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

"""SSH connection to Swift servers, helper functions."""

import paramiko
import logging
import subprocess

import destroystack.tools.common as common

LOG  = logging.getLogger(__name__)


def create_servers(configs):
    """Create Server objects out of a list of server configuration dicts."""
    servers = []
    for config in configs:
        servers.append(Server(**config))
    return servers


class ServerException(Exception):
    """ Raised when there was a problem executing an SSH command on a server.
    """
    pass


class LocalServer():
    def cmd(self, cmd, **kwargs):
        """Wrapper around subprocess.check_call() for logging purposes."""
        LOG.info("Running local command: %s", cmd)
        output = subprocess.check_call(cmd, shell=True, **kwargs)
        if output:
            LOG.info("Output: %s", output)
        return output


class Server(object):
    """ Manage server.

    Maintains an SSH connection to the server, keeps track of disks and their
    mount points.
    """
    def __init__(self, hostname,
            username="root", password=None, extra_disks=None, **kwargs):
        self.hostname = hostname
        self.name = common.get_name_from_hostname(hostname)
        self.disks = extra_disks
        if "root_password" in kwargs and not password:
            username = "root"
            password = kwargs["root_password"]

        self.cmd = SSH(hostname)
        self.cmd.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.cmd.load_system_host_keys()
        self.cmd.connect(hostname, username=username, password=password)

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
        self.cmd("umount --force -l /dev/" + disk)
        return disk

    def safe_umount_disk(self, disk):
        """ Umount disk if it is mounted.

        TODO: wait a bit if the device is busy
        """
        if disk in self.get_mount_points().keys():
            self.cmd("umount /dev/%s"% disk)

    def format_disk(self, disk):
        LOG.info("Formatting disk /dev/%s on %s", disk, self.name)
        assert disk not in self.get_mounted_disks()
        assert disk in self.disks
        self.cmd("mkfs.ext4 /dev/" + disk)

    def restore_disk(self, disk):
        """ Mount disk, restore permissions and SELinux contexts.

        If some other method of killing disks is later used, this will change
        to use something else than mount.
        """
        assert disk not in self.get_mounted_disks()
        LOG.info("Restoring disk /dev/%s on %s", disk, self.name)
        self.cmd("mount /dev/" + disk)
        self.cmd("chown -R swift:swift /srv/node/*")
        self.cmd("restorecon -R /srv/*")

    def get_mount_points(self):
        """ Get dict {disk:mountpoint} of mounted and managed disks.

        Only the disks given in configuration file (extra_disks) are taken into
        consideration. Unmounted disks are not included.
        Example: {"sda":"/srv/node/device1"}
        """
        mount_points = dict()
        for disk in self.disks:
            _, stdout, _ = self.cmd(
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
    """Wrapper around paramiko for better error handling and logging."""

    def __init__(self, hostname):
        super(SSH, self).__init__()
        self.hostname = hostname
        self.name = common.get_name_from_hostname(hostname)

    def __call__(self, command, ignore_failure=False, log_error=True):
        """ Same as exec_command, but checks for errors.

        If an error occurs, it logs the command, stdout and stderr.

        :param command: any bash command
        :param ignore_failure: don't raise an exception if an error occurs (and
            don't log the output either)
        :param log_error: if an error occurs, log the command, stdout and stderr
        :raises: ServerException
        """
        LOG.info("SSH command on %s: %s", self.name, command)
        stdin, stdout, stderr = self.exec_command(command)
        if not ignore_failure and stdout.channel.recv_exit_status() != 0:
            err = " ".join(stderr.readlines())
            if log_error:
                LOG.info("SSH command stdout:\n" + " ".join(stdout.readlines()))
                LOG.error("SSH command stderr:\n" + err)
            raise ServerException(err)
        return stdin, stdout, stderr
