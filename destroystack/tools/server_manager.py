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

# Possible roles that a server can have, depending what services are installed
# on it. It can have more than one role.
ROLES = ['keystone', 'swift_proxy', 'swift_data', 'controller', 'compute',
         'glance', 'cinder', 'neutron']

MANAGEMENT_TYPES = ['none', 'manual', 'openstack']

LOG = logging.getLogger(__name__)


class ServerManager(object):

    def __init__(self, config, connect=True):
        self._config = config

    def get(self, role=None, roles=None):
        """Get a server by its parameters.

        If no parameters are given, it will just return any of them.
        :param role: get a server that has this role, choose from `ROLES`
        :param roles: get a server that has all of these roles, see param
            `role`
        :param connect: if True, will create ssh connections to all the servers
        """
        if role:
            assert role in ROLES
        # you can use only one of them
        assert bool(role) != bool(roles)

    def get_all(self, role=None, roles=None):
        """Get a list of servers that have the given parameters.

        Same as `ServerManager.get`, but gets you a list of all the servers
        that fulfill the conditions, not just one.
        """
        pass

    def save_state(self, tag=''):
        """Create a snapshot of all the servers

        Depending on what is in the configuration in "management.type":
            * manual - Just create some backup of the files and maybe
                databases.  Unsupported and not recommended.
            * none - Do nothing
            * openstack - Create a snapshot of all the servers in the config

        If it's being created, the name of the snapshots (if created) will be
        "config.management.snapshot_prefix" + name of the VM + tag, where the
        prefix is "destroystack-snapshot" by default. The VMs have to have
        unique names (at least among each other) and snapshots/images with that
        name cannot already exist.

        :param tag: will be appended to the name of the snapshots
        """
        self._choose_sate_restoration_action('save', tag)

    def load_state(self, tag=''):
        """Restore all the servers from their snapshots.

        For more information, see the function ``save``.

        Depending on what is in the configuration in "management.type":
            * manual - Restore backups, mount disks that got umounted, start up
                services again. Unsupported, might not work - it's just a best
                effort.
            * none - Do nothing
            * openstack - Rebuild the VMs with the snapshot images, which are
                going to be found by the name as described in the `save`
                function.
        """
        self._choose_sate_restoration_action('load', tag)

    def connect(self):
        """Create ssh connections to all the servers.

        Will re-create them if called a second time.
        """
        pass

    def _choose_state_restoration_action(self, action, tag):
        """Choose which function to use, based on "management.type" in config.

        :param action: save or load
        """
        assert action in ['save', 'load']
        man_type = self._config['management']['type']

        if man_type == 'openstack':
            if action == 'save':
                state_restoration.openstack.create_snapshots(tag)
            else:
                state_restoration.openstack.restore_snapshots(tag)
        elif man_type == 'vagrant':
            raise NotImplementedError("vagrant snapshots unavailable")
        elif man_type == 'manual':
            if action == 'save':
                state_restoration.manual.create_backup(tag)
            else:
                state_restoration.manual.restore_backup(tag)
        elif man_type == 'none':
            LOG.info("State save and restoration has been turned off")
            pass
        else:
            raise Exception("This type of server management, '%s', is not"
                            "supported, choose among: %s"
                            % (man_type, MANAGEMENT_TYPES))
