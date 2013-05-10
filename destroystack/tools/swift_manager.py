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

""" Swift management and connection """

import swiftclient
import logging
import requests
from time import sleep
import destroystack.tools.config as config
import destroystack.tools.servers as servers
from destroystack.tools.timeout import timeout

LOG  = logging.getLogger(__name__)
CONFIG = config.Config()

def get_tiny_setup_manager():
    """ Return a SwiftManager for the tiny setup.

    Expects that packstack has already run with the correct answer file.

    NOTE: this will be replaced by some general resource broker that will decide
    which servers to use for what and perhaps even allow parallel run if enough
    servers are available (for example, if you have 6 servers, then the first 3
    would have its own Swift installation and run half the tiny_setup tests, the
    other 3 would have an independent Swift installation and run the rest of
    them)
    """
    proxy_conf, data_conf = config.get_tiny_setup_conf(CONFIG)
    proxies = servers.create_servers(proxy_conf)
    data_servers = servers.create_servers(data_conf)
    return SwiftManager(proxy_servers=proxies, data_servers=data_servers,
                        **CONFIG.keystone)


class SwiftManager(swiftclient.client.Connection):
    """ Manage Swift servers and connection.

    :param auth_url: URL of keystone service
    :param username: keystone user
    :param password: keystone password
    :param proxy_servers: list of Server objects that run the Swift services
    :param data_servers: list of Server objects that have extra disks
    """
    def __init__(self, auth_url, username, password,
                 proxy_servers, data_servers, **kwargs):
        super(SwiftManager, self).__init__(auth_url, username, password,
            auth_version='2', tenant_name=username)
        self.proxy_servers = proxy_servers
        self.data_servers = data_servers
        self._set_mount_check()
        self._backup()

    def replicas_are_ok(self, replica_count=3):
        """ Check if all objects and containers have enough replicas.

        If no replicas of the object or container are left (so they got removed
        completely), this method will not be able to recognize that and will
        return True if all the other data (which were not lost) have enough
        replicas.

        TODO: check account replicas too

        :returns: True iff there are 'replica_count' replicas of everything
        """
        account = self._get_account_hash()
        containers = [c['name'] for c in self.get_account()[1]]

        # check objects
        for container in containers:
            objects = [o['name'] for o in self.get_container(container)[1]]
            for obj in objects:
                urls = self._get_replicas_direct_urls(account, container, obj)
                if not file_urls_ok(urls, "object " + obj, replica_count):
                    return False

        # check containers
        for container in containers:
            urls = self._get_replicas_direct_urls(account, container)
            if not file_urls_ok(urls, "container " + container, replica_count):
                return False

        LOG.info("all replicas found")
        return True

    @timeout(CONFIG.timeout, "The replicas were not consistent within timeout.")
    def wait_for_replica_regeneration(self, replica_count=3):
        """ Wait until there are 'replica_count' replicas of everything.

        :raises TimeoutException: after time in seconds set in the config file
        """
        while not self.replicas_are_ok(replica_count):
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
                server.ssh.run("""
                    service rsyslog restart && service memcached restart &&
                    cd /etc/swift &&
                    rm -fr *.builder *.ring.gz backups """)
            for server in self.data_servers:
                server.ssh.run("rm -f /var/cache/swift/*.recon")
                for disk in server.disks:
                    server.safe_umount_disk(disk)
                server.ssh.run("rm -fr /srv/node/device*/*")
                for disk in server.disks:
                    server.ssh.run("mkfs.ext4 /dev/%s && mount /dev/%s"
                                    % (disk, disk))
        finally:
            self._restore()

    def _set_mount_check(self, restart_services=False):
        """ Set the parameter mount_check to True in /etc/swift/*-server.conf

        If this is not checked True, Swift will replicate files onto the
        system disk if the disk is umounted.
        """
        for server in self.data_servers:
            server.ssh.run("""
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
                server.ssh.run("""
                    rm -fr /var/tmp/swift-backup/etc &&
                    mkdir -p /var/tmp/swift-backup/etc &&
                    cd /etc/swift &&
                    cp -r *.builder *.ring.gz /var/tmp/swift-backup/etc/""")

            for server in self.data_servers:
                cmd = """
                    rm -fr /var/tmp/swift-backup/{devices,cache};
                    mkdir -p /var/tmp/swift-backup/{devices,cache} &&
                    cp /var/cache/swift/*.recon /var/tmp/swift-backup/cache/ """
                for device in server.get_mount_points().values():
                    cmd += "&& cp -r %s /var/tmp/swift-backup/devices/" % device
                server.ssh.run(cmd)
        finally:
            self._start_services()

    def _restore(self):
        """ Restore backups of Swift made by '_backup()'.

        Symmetric method to '_backup'. Brings Swift back to the state where it
        was when making the backup. While doing this, Swift services are stopped
        and then started again.
        """
        self._stop_services()
        for server in self.proxy_servers:
            server.ssh.run("cp -r /var/tmp/swift-backup/etc/* /etc/swift/ ")
        for server in self.data_servers:
            cmd = []
            for device in server.get_mount_points().values():
                cmd.append("cp -r /var/tmp/swift-backup/devices/* /srv/node/")
                server.ssh.run(" && ".join(cmd))
            server.ssh.run("chown -R swift:swift /srv/node/*")
            server.ssh.run(
                "cp -r /var/tmp/swift-backup/cache/* /var/cache/swift/")
        self._start_services()

    def _stop_services(self):
        for server in self.proxy_servers + self.data_servers:
            try:
                server.ssh.run("swift-init all stop", log_error=False)
            except servers.ServerException:
                # 'swift-init all stop' returns non-zero if the services are
                # already stopped, so check if this is the case
                services = self._get_running_services(server)
                if len(services) > 0:
                    raise servers.ServerException(
                        "Could not stop Swift services: %s" % services)

    def _start_services(self):
        for server in self.data_servers:
            server.ssh.run("swift-init account container object rest start")
        for server in self.proxy_servers:
            server.ssh.run("swift-init proxy start")

    def _restart_services(self):
        for server in self.data_servers:
            server.ssh.run("swift-init account container object rest restart")
        for server in self.proxy_servers:
            server.ssh.run("swift-init proxy restart")

    def _get_running_services(self, server):
        _, stdout, _ = server.ssh.run("swift-init all status",
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

        The first 'replica_count' items returned are primarily locations where
        the data will be unless there was a failure, the rest will be handoff
        nodes where the data will be only if there was a failure in the
        primarily locations (the number of them depends on the number of nodes
        there are).
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
        _, stdout, _ = self.proxy_servers[0].ssh.run(cmd)
        urls = [line.split('#')[0].split()[-1].strip('"\n ')
                    for line in stdout.readlines()]
        return urls


def file_urls_ok(urls, name, count=3, exact_count=False):
    """ Go trough all URLs of the file and check if at least 'count' responded.

    :param name: for logging output, should be something like "object 'file123'"
    :param exact_count: also return False if more than 'count' were OK
    """
    found = 0
    for url in urls:
        r = requests.get(url)
        if r.status_code in [200, 204]:
            found += 1
        else:
            LOG.debug("file not found on %s", url)
        if not exact_count and found == count:
            break
    if found < count:
        LOG.warning("Found only %i copies of %s", found, name)
        return False
    elif exact_count and found > count:
        return False
    else:
        return True
