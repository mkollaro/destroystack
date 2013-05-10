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

        self.ssh = SSH(hostname)
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.load_system_host_keys()
        self.ssh.connect(hostname, username="root", password=root_password)

        self.disks = extra_disks
        self._mount_points = dict()
        self.get_mount_points()

    def kill_disk(self):
        """ Force umount one of the mounted disks.

        TODO: REALLY force it
        TODO: perhaps use
            https://www.kernel.org/doc/Documentation/device-mapper/dm-flakey.txt
        """
        assert self.disks is not None
        available_disks = list(self.get_mount_points().keys())
        if not available_disks:
            raise Exception("No available disks")
        disk = available_disks[0]
        self.ssh.run("umount --force -l /dev/" + disk)

    def safe_umount_disk(self, disk):
        """ Umount disk if it is mounted.

        TODO: wait a bit if the device is busy
        """
        if disk in self.get_mount_points().keys():
            self.ssh.run("umount /dev/%s"% disk)

    def get_mount_points(self):
        if self.disks is None:
            return dict()

        self._mount_points = dict()
        for disk in self.disks:
            _, stdout, _ = self.ssh.run(
                "mount|grep /dev/%s| awk '{print $3}'" % disk)
            output = stdout.readlines()
            if output:
                self._mount_points[disk] = output[0].strip()
        return self._mount_points


class SSH(paramiko.SSHClient):
    """ Wrapper around paramiko for better error handling and logging. """

    def __init__(self, hostname):
        super(SSH, self).__init__()
        self.hostname = hostname

    def run(self, command, ignore_failure=False, log_error=True):
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
