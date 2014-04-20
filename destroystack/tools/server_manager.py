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

import logging
from destroystack.tools import state_restoration
import destroystack.tools.servers as server_tools

# Possible roles that a server can have, depending what services are installed
# on it. It can have more than one role.
ROLES = set(['keystone', 'swift_proxy', 'swift_data', 'controller', 'compute',
             'glance', 'cinder', 'neutron'])

MANAGEMENT_TYPES = ['none', 'manual', 'metaopenstack']

LOG = logging.getLogger(__name__)


class ServerManager(object):

    def __init__(self, config):
        """
        :param config: path to configuration file, should be the one which was
            generated from the main one and contains roles for each server
        """
        self._config = config
        self._servers = server_tools.create_servers(config['servers'])

    def servers(self, role=None, roles=None):
        """Generator that gets a server by its parameters.

        If no parameters are given, it will just return any of them.
        :param role: get a server that has this role, choose from `ROLES`
        :param roles: get a server that has all of these roles, see param
            `role`
        """
        if role:
            assert role in ROLES
            assert not roles  # cannot use both
        if roles:
            roles = set(roles)
            assert roles.issubset(ROLES)

        for server in self._servers:
            if not role and not roles:
                # no conditions, return any
                yield server
            elif role in server.roles \
                    or (roles and roles.issubset(server.roles)):
                yield server

    def get(self, role=None, roles=None):
        """Get the first server that matches the parameters.

        For more info, look at the `ServerManager.servers() generator - it uses
        the same parameters.
        :returns: the server in question or None
        """
        try:
            return self.servers(role, roles).next()
        except StopIteration:
            return None

    def save_state(self, tag=''):
        """Create a snapshot of all the servers

        Depending on what is in the configuration in "management.type":
            * manual - Just create some backup of the files and maybe
                databases.  Unsupported and not recommended.
            * none - Do nothing
            * metaopenstack - Create a snapshot of all the servers

        If it's being created, the name of the snapshots (if created) will be
        "config.management.snapshot_prefix" + name of the VM + tag, where the
        prefix is "destroystack-snapshot" by default. The VMs have to have
        unique names (at least among each other) and snapshots/images with that
        name cannot already exist.

        :param tag: will be appended to the name of the snapshots
        """
        self._choose_state_restoration_action('save', tag)

    def load_state(self, tag=''):
        """Restore all the servers from their snapshots.

        For more information, see the function ``save``.

        Depending on what is in the configuration in "management.type":
            * manual - Restore backups, mount disks that got umounted, start up
                services again. Unsupported, might not work - it's just a best
                effort.
            * none - Do nothing
            * metaopenstack - Rebuild the VMs with the snapshot images, which
                are going to be found by the name as described in the `save`
                function.
        """
        self._choose_state_restoration_action('load', tag)

    def connect(self):
        """Create ssh connections to all the servers.

        Will re-create them if called a second time.
        """
        self._servers = server_tools.create_servers(self._config['servers'])

    def _choose_state_restoration_action(self, action, tag):
        """Choose which function to use, based on "management.type" in config.

        :param action: save or load
        """
        assert action in ['save', 'load']
        man_type = self._config['management']['type']

        if man_type == 'metaopenstack':
            if action == 'save':
                state_restoration.metaopenstack.create_snapshots(tag)
            else:
                state_restoration.metaopenstack.restore_snapshots(tag)
        elif man_type == 'vagrant':
            raise NotImplementedError("vagrant snapshots unavailable")
        elif man_type == 'manual':
            if action == 'save':
                state_restoration.manual.create_backup(self)
            else:
                state_restoration.manual.restore_backup(self)
        elif man_type == 'none':
            LOG.info("State save and restoration has been turned off")
        else:
            raise Exception("This type of server management, '%s', is not"
                            "supported, choose among: %s"
                            % (man_type, MANAGEMENT_TYPES))

    def _single_disk_workaround(self):
        """Use the partitions of the disk instead of the single disk

        If only one disk was given, then the deployment actually partitioned it
        so that we can have storage devices.
        TODO: check if the partitions actually exist
        """
        for server in self.servers(role='swift_data'):
            if len(server.disks) == 1:
                disk = server.disks[0]
                partitions = [disk+"1", disk+"2", disk+"3"]
                server.disks = partitions
