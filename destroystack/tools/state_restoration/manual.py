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

"""Manual backup and restoration of servers.

Not recommended - only best effort. It may cause false negatives - the state
might not get completely restored and cause tests to fail. If possible, use the
metaopenstack snapshotting.


Currently only supports Swift. You need to either use a different state
restoration method or add support for the component you need if Swift is not
what you are testing.

It will try to back up all the files (and in the future databases) that keep
the state of the servers. After some fail injection test runs and probably
causes damage to something, this can be restored and services restarted, thus
bringing the machine into the same state as it was before, and another test can
run.
"""

import logging
import destroystack.tools.servers as servers

LOG = logging.getLogger(__name__)


def create_backup(server_manager):
    """Create backup of configuration and files that keep state.

    Only Swift is supported so far.

    Symmetric function to 'restore_backup'. Backs up all .builder and .ring.gz
    on the proxy servers, disk content of Swift disks and .recon files on the
    data servers. While doing this, all Swift services are stopped and then
    started again.
    """
    swift_proxy_servers = list(server_manager.servers(role='swift_proxy'))
    swift_data_servers = list(server_manager.servers(role='swift_data'))
    LOG.info("Saving Swift state")
    try:
        stop_swift_services(swift_proxy_servers, swift_data_servers)
        for server in swift_proxy_servers:
            server.cmd("""
                rm -fr /root/swift-backup/etc &&
                mkdir -p /root/swift-backup/etc &&
                cd /etc/swift &&
                cp -rp *.builder *.ring.gz /root/swift-backup/etc/""")
        for server in swift_data_servers:
            server.cmd("rm -fr /root/swift-backup/{devices,cache}")
            server.cmd("mkdir -p /root/swift-backup/{devices,cache}")
            server.cmd(
                "cp -p /var/cache/swift/* /root/swift-backup/cache/",
                ignore_failure=True)
            for device in server.get_mount_points().values():
                server.cmd("cp -rp %s /root/swift-backup/devices/"
                           % device)
    finally:
        start_swift_services(swift_proxy_servers, swift_data_servers)


def restore_backup(server_manager):
    """Try to remove changes made to the system since running `create_backup`.

    Only Swift is supported so far.

    Symmetric function to `create_backup`. Cleans and re-mounts disks on
    data servers. Restores rings and builder files, restarts swift services.
    """
    swift_proxy_servers = list(server_manager.servers(role='swift_proxy'))
    swift_data_servers = list(server_manager.servers(role='swift_data'))
    try:
        stop_swift_services(swift_proxy_servers, swift_data_servers)
        for server in swift_proxy_servers:
            server.cmd("""
                service rsyslog restart && service memcached restart &&
                cd /etc/swift &&
                rm -fr *.builder *.ring.gz backups """)
        for server in swift_data_servers:
            server.cmd("rm -f /var/cache/swift/*.recon")
            for disk in server.disks:
                server.umount(disk)
            server.cmd("rm -fr /srv/node/device*/*")
            for disk in server.disks:
                server.cmd("mkfs.ext4 /dev/%s && mount /dev/%s"
                           % (disk, disk))
    finally:
        _restore_backup_files(server_manager)


def _restore_backup_files(server_manager):
    """ Restore backups of Swift made by '_backup()'.

    Symmetric method to '_backup'. Brings Swift back to the state where it
    was when making the backup. While doing this, Swift services are
    stopped and then started again.
    """
    swift_proxy_servers = list(server_manager.servers(role='swift_proxy'))
    swift_data_servers = list(server_manager.servers(role='swift_data'))
    LOG.info("Restoring Swift state")
    try:
        stop_swift_services(swift_proxy_servers, swift_data_servers)
        for server in swift_proxy_servers:
            server.cmd("cp -rp /root/swift-backup/etc/* /etc/swift/ ")
        for server in swift_data_servers:
            for _ in server.get_mount_points().values():
                server.cmd(
                    "cp -rp /root/swift-backup/devices/* /srv/node/")
            server.cmd("chown -R swift:swift /srv/node/*")
            server.cmd("restorecon -R /srv/*")
            server.cmd(
                "cp -rp /root/swift-backup/cache/* /var/cache/swift/",
                ignore_failure=True)
    finally:
        start_swift_services(swift_proxy_servers, swift_data_servers)


def stop_swift_services(proxy_servers, data_servers):
    for server in proxy_servers + data_servers:
        try:
            server.cmd("swift-init all stop", log_error=False)
        except servers.ServerException:
            # 'swift-init all stop' returns non-zero if the services are
            # already stopped, so check if this is the case
            services = get_running_swift_services(server)
            if len(services) > 0:
                raise servers.ServerException(
                    "Could not stop Swift services: %s" % services)


def start_swift_services(proxy_servers, data_servers):
    for server in data_servers:
        server.cmd("swift-init account container object rest start")
    for server in proxy_servers:
        server.cmd("swift-init proxy start")


def restart_swift_services(proxy_servers, data_servers):
    for server in data_servers:
        server.cmd("swift-init account container object rest restart")
    for server in proxy_servers:
        server.cmd("swift-init proxy restart")


def get_running_swift_services(server):
    output, _ = server.cmd("swift-init all status", ignore_failure=True)
    return [line.split()[0] for line in output
            if not line.startswith("No ")]
