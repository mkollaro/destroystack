#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#           http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import swiftclient
import logging
import requests
from time import sleep
import destroystack.tools.servers as servers
import destroystack.tools.common as common
from destroystack.tools.timeout import timeout

LOG  = logging.getLogger(__name__)
TIMEOUT = common.get_timeout()


class SwiftManager(swiftclient.client.Connection):
    """Manage Swift servers and connection.

    :param config: dictionary created by "bin/generate_config_files.py", needs
        a "keystone" item with "auth_url", "user" and "password" items and a
        "swift" item with "proxy_servers" and "data_servers".
    """
    def __init__(self, config):
        keystone = config["keystone"]
        super(SwiftManager, self).__init__(
            keystone["auth_url"],
            keystone["user"],
            keystone["password"],
            auth_version='2',
            tenant_name=keystone["user"])
        self.proxy_servers = \
            servers.create_servers(config["swift"]["proxy_servers"])
        self.data_servers = \
            servers.create_servers(config["swift"]["data_servers"])
        self._set_mount_check()
        self._backup()

    def replicas_are_ok(self, count=3, check_nodes=None, exact=False):
        """ Check if all objects and containers have enough replicas.

        If no replicas of the object or container are left (so they got removed
        completely), this method will not be able to recognize that and will
        return True if all the other data (which were not lost) have enough
        replicas.

        TODO: check account replicas too

        :param check_nodes: Look only at first x number of nodes. Since usually
            the first 'count' nodes are primary nodes, if you set
            'check_nodes=count', no handoff nodes will be checked out. If
            set to None, try all of them.
        :param exact: also fail if there are more than 'count' replicas
        :returns: True iff there are 'count' replicas of everything
        """
        account = self._get_account_hash()
        containers = [c['name'] for c in self.get_account()[1]]

        # check objects
        for container in containers:
            objects = [o['name'] for o in self.get_container(container)[1]]
            for obj in objects:
                urls = self._get_replicas_direct_urls(account, container, obj)
                if not file_urls_ok(urls, "object " + obj, count, check_nodes,
                                    exact):
                    return False

        # check containers
        for container in containers:
            urls = self._get_replicas_direct_urls(account, container)
            if not file_urls_ok(urls, "container " + container, count,
                                check_nodes, exact):
                return False

        LOG.info("all replicas found")
        return True

    @timeout(TIMEOUT, "The replicas were not consistent within timeout.")
    def wait_for_replica_regeneration(self, count=3, check_nodes=None,
                                      exact=False):
        """ Wait until there are 'count' replicas of everything.

        :param check_nodes: Look only at first x number of nodes. Since usually
            the first 'count' nodes are primary nodes, if you set
            'check_nodes=count', no handoff nodes will be checked out. If
            set to None, try all of them.
        :param exact: also fail if there are more than 'count' replicas
        :raises TimeoutException: after time in seconds set in the config file
        """
        while not self.replicas_are_ok(count, check_nodes, exact):
            sleep(5)

    def reset(self):
        """ Remove all changes made to Swift since creating this object.

        Useful to clean state between test cases. Cleans and re-mounts disks on
        data servers. Restores rings and builder files, restarts swift services
        on proxy servers.
        """
        try:
            self._stop_services()
            for server in self.proxy_servers:
                server.ssh("""
                    service rsyslog restart && service memcached restart &&
                    cd /etc/swift &&
                    rm -fr *.builder *.ring.gz backups """)
            for server in self.data_servers:
                server.ssh("rm -f /var/cache/swift/*.recon")
                for disk in server.disks:
                    server.safe_umount_disk(disk)
                server.ssh("rm -fr /srv/node/device*/*")
                for disk in server.disks:
                    server.ssh("mkfs.ext4 /dev/%s && mount /dev/%s"
                                    % (disk, disk))
        finally:
            self._restore()

    def _set_mount_check(self, restart_services=False):
        """ Set the parameter mount_check to True in /etc/swift/*-server.conf

        If this is not checked True, Swift will replicate files onto the
        system disk if the disk is umounted.
        """
        for server in self.data_servers:
            server.ssh("""
                sed -i -e 's/mount_check.*=.*false/mount_check = true/' \
                /etc/swift/*-server.conf""")
        if restart_services:
            self._restart_services()

    def _backup(self):
        """ Create backups of Swift files that keeps state and disk content.

        Symmetric method to '_restore'. Backs up all .builder and .ring.gz on
        the proxy servers, disk content of Swift disks and .recon files on the
        data servers. While doing this, all Swift services are stopped and then
        started again.
        """
        try:
            self._stop_services()
            for server in self.proxy_servers:
                server.ssh("""
                    rm -fr /var/tmp/swift-backup/etc &&
                    mkdir -p /var/tmp/swift-backup/etc &&
                    cd /etc/swift &&
                    cp -rp *.builder *.ring.gz /var/tmp/swift-backup/etc/""")
            for server in self.data_servers:
                server.ssh("rm -fr /var/tmp/swift-backup/{devices,cache}")
                server.ssh("mkdir -p /var/tmp/swift-backup/{devices,cache}")
                server.ssh(
                    "cp -p /var/cache/swift/* /var/tmp/swift-backup/cache/",
                    ignore_failure=True)
                for device in server.get_mount_points().values():
                    server.ssh("cp -rp %s /var/tmp/swift-backup/devices/"
                                    % device)
        finally:
            self._start_services()

    def _restore(self):
        """ Restore backups of Swift made by '_backup()'.

        Symmetric method to '_backup'. Brings Swift back to the state where it
        was when making the backup. While doing this, Swift services are stopped
        and then started again.
        """
        try:
            self._stop_services()
            for server in self.proxy_servers:
                server.ssh("cp -rp /var/tmp/swift-backup/etc/* /etc/swift/ ")
            for server in self.data_servers:
                for device in server.get_mount_points().values():
                    server.ssh(
                        "cp -rp /var/tmp/swift-backup/devices/* /srv/node/")
                server.ssh("chown -R swift:swift /srv/node/*")
                server.ssh("restorecon -R /srv/*")
                server.ssh(
                    "cp -rp /var/tmp/swift-backup/cache/* /var/cache/swift/",
                    ignore_failure=True)
        finally:
            self._start_services()

    def _stop_services(self):
        for server in self.proxy_servers + self.data_servers:
            try:
                server.ssh("swift-init all stop", log_error=False)
            except servers.ServerException:
                # 'swift-init all stop' returns non-zero if the services are
                # already stopped, so check if this is the case
                services = self._get_running_services(server)
                if len(services) > 0:
                    raise servers.ServerException(
                        "Could not stop Swift services: %s" % services)

    def _start_services(self):
        for server in self.data_servers:
            server.ssh("swift-init account container object rest start")
        for server in self.proxy_servers:
            server.ssh("swift-init proxy start")

    def _restart_services(self):
        for server in self.data_servers:
            server.ssh("swift-init account container object rest restart")
        for server in self.proxy_servers:
            server.ssh("swift-init proxy restart")

    def _get_running_services(self, server):
        _, stdout, _ = server.ssh("swift-init all status",
                        ignore_failure=True)
        return [line.split()[0] for line in stdout.readlines()
                if not line.startswith("No ")]

    def _get_account_hash(self):
        """ Gets the Swift account hash of the currently connected user.

        Note: shouldn't there be a nicer way to do this in swiftclient?
        """
        return self.url.split('/')[-1]

    def _get_replicas_direct_urls(self, account_hash, container_name=None,
                                 object_name=None):
        """ Return a tuple of the URLs of replicas.

        The returned URLs are where the account/container/object replicas can be
        directly accessed. The object (or anything else) doesn't actually need
        to exist, it will give you a URL where it would exist if you created it.

        The first 'replica_count' (normally set to 3) items returned are
        primarily locations where the data will be unless there was a failure,
        the rest will be handoff nodes where the data will be only if there was
        a failure in the primarily locations (the number of them depends on the
        number of nodes there are).
        """
        ring = ''
        if object_name is not None and container_name is not None:
            ring = "object"
        elif container_name is not None:
            ring = "container"
            object_name = ''
        else:
            ring = "account"
            container_name = ''
            object_name = ''
        cmd = "swift-get-nodes -a /etc/swift/%s.ring.gz %s %s %s |grep curl" \
                % (ring, account_hash, container_name, object_name)
        _, stdout, _ = self.proxy_servers[0].ssh(cmd)
        urls = [line.split('#')[0].split()[-1].strip('"\n ')
                    for line in stdout.readlines()]
        return urls


def file_urls_ok(urls, name, count=3, check_url_count=None, exact=False):
    """ Go trough URLs of the file and check if at least 'count' responded.

    :param name: for logging output, should be something like "object file123"
    :param count: how many URLs need to be valid
    :param check_url_count: try only first x number of the URLs. If set to
        None, try all.
    :param exact: also fail if there are more than 'count' replicas
    """
    found = 0
    for url in urls[:check_url_count]:
        r = requests.get(url)
        if r.status_code in [200, 204]:
            found += 1
        else:
            LOG.debug("file not found on %s", url)
        if not exact and found == count:
            break
    if found < count:
        LOG.warning("Found only %i copies of '%s'", found, name)
        return False
    elif exact and found > count:
        LOG.warning("Found %i copies of '%s', which is more then should be",
            found, name)
        return False
    else:
        return True
