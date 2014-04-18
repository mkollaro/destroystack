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
from socket import gethostbyname

import destroystack.tools.common as common

LOG = logging.getLogger(__name__)


def create_servers(configs):
    """Create Server objects out of a list of server configuration dicts."""
    servers = []
    for config in configs:
        servers.append(Server(**config))
    return servers


class ServerException(Exception):
    """ Raised when there was a problem executing an SSH command on a server.
    """
    def __init__(self, hostname, message, **kwargs):
        new_msg = "[%s] %s" % (hostname, message)
        super(ServerException, self).__init__(new_msg, **kwargs)


class LocalServer():
    def cmd(self, cmd, log_cmd=True, log_output=True, **kwargs):
        """Wrapper around subprocess.check_call() for logging purposes."""
        if log_cmd:
            LOG.info("Running local command: %s", cmd)
        output = subprocess.check_call(cmd, shell=True, **kwargs)
        if log_output and output:
            LOG.info("Output: %s", output)
        return output


class Server(object):
    """ Manage server.

    Maintains an SSH connection to the server, keeps track of disks and their
    mount points.
    """
    def __init__(self, hostname=None, ip=None, username="root", password=None,
                 roles=None, extra_disks=None, **kwargs):
        assert hostname or ip, "either hostname or IP address required"
        self.hostname = hostname
        if not ip:
            self.ip = gethostbyname(self.hostname)
        else:
            self.ip = ip
        self.name = self._decide_on_name()
        self.roles = roles or set()
        self.disks = extra_disks
        if "root_password" in kwargs and not password:
            username = "root"
            password = kwargs["root_password"]

        self.cmd = SSH(self.name)
        self.cmd.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.cmd.load_system_host_keys()
        self.cmd.connect(hostname, username=username, password=password)

    def __str__(self):
        return self.name

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

    def umount(self, disk):
        """ Umount disk if it is mounted.

        TODO: wait a bit if the device is busy
        """
        if disk in self.get_mount_points().keys():
            self.cmd("umount /dev/%s" % disk)

    def format_disk(self, disk):
        LOG.info("Formatting disk /dev/%s on %s", disk, self.name)
        assert disk not in self.get_mounted_disks()
        assert disk in self.disks
        self.cmd("mkfs.ext4 -F /dev/" + disk)

    def format_extra_disks(self):
        cmd = ["(mkfs.ext4 -F /dev/%s > /dev/null)&" % d for d in self.disks]
        cmd.append("wait")
        self.cmd(" ".join(cmd))

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
            stdout, _ = self.cmd(
                "mount|grep '/dev/%s '| awk '{print $3}'" % disk)
            if stdout:
                mount_points[disk] = stdout[0].strip()
        return mount_points

    def get_mounted_disks(self):
        """ Return list of disk names like "sda".
        """
        return list(self.get_mount_points().keys())

    def _decide_on_name(self):
        if not self.hostname:
            return self.ip

        # if it's just a short name, use that
        if '.' not in self.hostname:
            return self.hostname
        # if it's a long hostname, use first part
        name = self.hostname.split('.')[0]
        if common.represents_int(name):
            # not really a hostname, just IP - which didn't get specified in
            # the 'ip' field as it should have been
            name = self.hostname
        return name


class SSH(paramiko.SSHClient):
    """Wrapper around paramiko for better error handling and logging."""

    def __init__(self, name):
        super(SSH, self).__init__()

    def __call__(self, command, ignore_failure=False,
                 log_cmd=True, log_output=False, log_error=True):
        """ Similar to exec_command, but checks for errors.

        If an error occurs, it logs the command, stdout and stderr.

        :param command: any bash command
        :param ignore_failure: don't raise an exception if an error occurs (and
            don't log the output either)
        :param log_error: if an error occurs, log stdout and stderr; don't log
            them again if log_output is true
        :param log_output: always log output
        :param log_cmd: log the command and the name of server where it is run
        :raises: ServerException
        """
        if log_cmd:
            LOG.info("SSH command on %s: %s", self.name, command)
        _, stdout, stderr = self.exec_command(command)
        out = stdout.readlines()
        err = stderr.readlines()
        if log_output:
            _log_output(out, err)
        if not ignore_failure and stdout.channel.recv_exit_status() != 0:
            if log_error and not log_output:
                _log_output(out, err)
            raise ServerException(self.name, err)
        return out, err


def partition_single_extra_disk(server):
    """Workaround when only one disk is available and we need more

    When only one disk is available and we need 3 for Swift storage, create
    partitions on it and use those as extra "disks". Requires the disk to have
    at least 6GB and will delete everyting on it.
    """
    assert(len(server.disks) == 1)
    disk = server.disks[0]
    partition_table = '\n'.join([
        '# partition table of /dev/{0}',
        'unit: sectors',
        '/dev/{0}1 : start=       63, size=  4195233, Id=83',
        '/dev/{0}2 : start=  4195296, size=  4195296, Id=83',
        '/dev/{0}3 : start=  8390592, size=  4192272, Id=83',
        '/dev/{0}4 : start=        0, size=        0, Id= 0'
    ]).format(disk)
    server.umount(disk)
    devices = server.cmd('ls /dev/%s*' % disk).split()
    if len(devices) == 4:  # one main disk device, 3 partitions
        LOG.info("Partitions of the disk '/dev/%s' already exist" % disk)
    elif 1 < len(devices) < 4:
        raise ServerException(server.name, "Partitions of '/dev/%s' exist, but"
                              " there is an incorrect number of them"
                              " - there should be 3 of them" % disk)
    else:
        LOG.info('Creating 3 partitions on %s:/dev/%s' % (server.name, disk))
        server.cmd('echo -e \'%s\' > partition_table' % partition_table)
        server.cmd('sfdisk /dev/%s < partition_table' % disk)
    partitions = [disk+'1', disk+'2', disk+'3']
    server.disks = partitions


def _log_output(stdout, stderr):
    if stdout:
        LOG.info("SSH command stdout:\n" + " ".join(stdout).strip())
    if stderr:
        LOG.error("SSH command stderr:\n" + " ".join(stderr).strip())


def prepare_extra_disks(servers):
    """Format and partition disks if neccessary.

    Return a list in form ["ip.address/vda", "ip.address.2/vda"]
    """
    description = list()
    for server in servers:
        if len(server.disks) == 1:
            LOG.info("Only one extra disk on %s, create partitions on it and"
                     " use those instead" % server)
            partition_single_extra_disk(server)
        LOG.info("Formatting extra disks on %s" % server)
        server.format_extra_disks()
        # get description of devices for packstack answerfile
        ip = gethostbyname(server.hostname)
        devices = ['/'.join([ip, disk]) for disk in server.disks]
        description.extend(devices)
    return description
