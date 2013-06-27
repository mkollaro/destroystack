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

""" SSH connection to Swift servers, helper functions. """

import paramiko
import logging

LOG  = logging.getLogger(__name__)


def create_servers(configs):
    servers = []
    for config in configs:
        servers.append(Server(**config))
    return servers


class ServerException(Exception):
    """ Raised when there was a problem executing an SSH command on a server.
    """
    pass


class Server(object):
    """ Manage server.

    Maintains an SSH connection to the server, keeps track of disks and their
    mount points.
    """
    def __init__(self, hostname,
            extra_disks=None, root_password=None, **kwargs):
        self.hostname = hostname
        self.name = hostname.split('.')[0]
        self.disks = extra_disks

        self.ssh = SSH(hostname)
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.load_system_host_keys()
        self.ssh.connect(hostname, username="root", password=root_password)

    def kill_disk(self, disk=None):
        """ Force umount one of the mounted disks.

        :param disk: name of disk in /dev/ on the server, for example "sda",
            use any available disk if None
        :returns: label of disk that was killed, for example "sda"
        TODO: REALLY force it, perhaps use
            https://www.kernel.org/doc/Documentation/device-mapper/dm-flakey.txt
        """
        available_disks = self.get_mounted_disks()
        if not available_disks:
            raise Exception("No available disks")
        if disk is None:
            disk = available_disks[0]
        assert disk in available_disks
        LOG.info("Killing disk /dev/%s on %s", disk, self.name)
        self.ssh("umount --force -l /dev/" + disk)
        return disk

    def safe_umount_disk(self, disk):
        """ Umount disk if it is mounted.

        TODO: wait a bit if the device is busy
        """
        if disk in self.get_mount_points().keys():
            self.ssh("umount /dev/%s"% disk)

    def format_disk(self, disk):
        LOG.info("Formatting disk /dev/%s on %s", disk, self.name)
        assert disk not in self.get_mounted_disks()
        assert disk in self.disks
        self.ssh("mkfs.ext4 /dev/" + disk)

    def restore_disk(self, disk):
        """ Mount disk, restore permissions and SELinux contexts.

        If some other method of killing disks is later used, this will change
        to use something else than mount.
        """
        assert disk not in self.get_mounted_disks()
        LOG.info("Restoring disk /dev/%s on %s", disk, self.name)
        self.ssh("mount /dev/" + disk)
        self.ssh("chown -R swift:swift /srv/node/*")
        self.ssh("restorecon -R /srv/*")

    def get_mount_points(self):
        """ Get dict {disk:mountpoint} of mounted and managed disks.

        Only the disks given in configuration file (extra_disks) are taken into
        consideration. Unmounted disks are not included.
        Example: {"sda":"/srv/node/device1"}
        """
        mount_points = dict()
        for disk in self.disks:
            _, stdout, _ = self.ssh(
                "mount|grep /dev/%s| awk '{print $3}'" % disk)
            output = stdout.readlines()
            if output:
                mount_points[disk] = output[0].strip()
        return mount_points

    def get_mounted_disks(self):
        """ Return list of disk names like "sda".
        """
        return list(self.get_mount_points().keys())


class SSH(paramiko.SSHClient):
    """ Wrapper around paramiko for better error handling and logging. """

    def __init__(self, hostname):
        super(SSH, self).__init__()
        self.hostname = hostname

    def __call__(self, command, ignore_failure=False, log_error=True):
        """ Same as exec_command, but checks for errors.

        If an error occurs, it logs the command, stdout and stderr.

        :param command: any bash command
        :param ignore_failure: don't raise an exception if an error occurs (and
            don't log the output either)
        :param log_error: if an error occurs, log the command, stdout and stderr
        :raises: ServerException
        """
        stdin, stdout, stderr = self.exec_command(command)
        if not ignore_failure and stdout.channel.recv_exit_status() != 0:
            err = " ".join(stderr.readlines())
            if log_error:
                LOG.info("SSH command on %s:\n%s", self.hostname, command)
                LOG.info("SSH command stdout:\n" + " ".join(stdout.readlines()))
                LOG.error("SSH command stderr:\n" + err)
            raise ServerException(err)
        return stdin, stdout, stderr
