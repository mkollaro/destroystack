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


"""Handle the state restoration of server.

Since destroystack injects failures into the tested system, there has to be
some isolation between tests, otherwise a failure caused by one test might
cause an unwanted failure in the next one.

This module can save and restore the state by various methods.  The type of
state restoration is decided in the configuration, "management.type", which can
be:
    * manual
    * none
    * openstack
    * vagrant (not implemented)
    * vagrant-libvirt (not implemented)
    * lvm (not implemented)

The basic one is of type 'manual' - it just backs up some files and restores
them after the tests, plus starts up the services that were turned off and
similar. It's just a best effort restoration - it takes a lot of work to get it
working properly and is not supported for everything. Try not to rely on it if
possible.

The better way is to use snapshots, although this requires that the servers are
VMs. Right now, only snapshots of OpenStack VMs is supported, but VirtualBox
(trough vagrant) and libvirt might get supported in the future. For bare metal,
using the LVM snapshots might get supported.
"""

import logging
import time
import itertools
from novaclient import client
from destroystack.tools.timeout import wait_for

LOG = logging.getLogger(__name__)


def save(config, tag=''):
    """Create a snapshot of all the servers

    Depending on what is in the configuration in "management.type":
        * manual - Just create some backup of the files and maybe databases.
            Unsupported and not recommended.
        * none - Do nothing
        * openstack - Create a snapshot of all the servers in the configuration

    If it's being created, the name of the snapshots (if created) will be
    "config.management.snapshot_prefix" + name of the VM + tag, where the
    prefix is "destroystack-snapshot" by default. The VMs have to have unique
    names (at least among each other) and snapshots/images with that name
    cannot already exist.

    :param tag: will be appended to the name of the snapshots
    """
    _choose_action(config, 'save', tag)


def load(config, tag=''):
    """Restore all the servers from their snapshots.

    For more information, see the function ``save``.

    Depending on what is in the configuration in "management.type":
        * manual - Restore backups, mount disks that got umounted, start up
            services again. Unsupported, might not work - it's just a best
            effort.
        * none - Do nothing
        * openstack - Rebuild the VMs with the snapshot images, which are going
            to be found by the name as described in the ``save`` function.
    """
    _choose_action(config, 'load', tag)


def delete(config, tag=''):
    """Delete all the snapshots of the servers.

    For more information, see the function ``save``.

    Depending on what is in the configuration in "management.type":
        * manual - Do nothing (removing the backup files is not implemented)
        * none - Do nothing
        * openstack - Remove all the snapshots with the names as described in
            the ``save`` function
    """
    _choose_action(config, 'delete', tag)


def _choose_action(config, action, tag):
    """Choose which function to use, based on "management.type" in config.

    :param action: save, load or delete
    """
    if 'management' not in config or 'type' not in config['management']:
        raise Exception("The management type has to be in config")
    assert action in ['save', 'load', 'delete']

    type = config['management']['type']
    if type == 'openstack':
        if action == 'save':
            create_openstack_snapshots(config, tag)
        elif action == 'load':
            load_openstack_snapshots(config, tag)
        else:
            delete_openstack_snapshots(config, tag)
    elif type == 'vagrant':
        raise NotImplementedError("vagrant snapshots are not implemented yet")
        #create_vagrant_snapshots(config, tag)
    elif type == 'manual':
        pass
        #create_manual_backup(config, tag)
    elif type == 'none':
        LOG.info("State save and restoration has been turned off")
    else:
        raise Exception


def create_openstack_snapshots(config, tag):
    """Create snapshots of OpenStack VMs and wait until they are active.
    """
    nova = _get_nova_client(config)
    vms = _find_openstack_vms(nova, config)

    snapshots = list()
    for vm_id in vms:
        vm = nova.servers.get(vm_id)
        snapshot_name = _get_snapshot_name(config, vm.name, tag)
        # maybe sync the filesystem first
        LOG.info("Creating snapshot '%s'" % snapshot_name)
        s = vm.create_image(snapshot_name)
        snapshots.append(s)
        time.sleep(5)

    for snapshot_id in snapshots:
        snapshot = nova.images.get(snapshot_id)
        wait_for("Waiting until snapshot '%s' is active" % snapshot.name,
                 lambda x: x.status == 'ACTIVE',
                 lambda: nova.images.get(snapshot_id),
                 timeout=180)


def load_openstack_snapshots(config, tag):
    """Restore snapshots of servers - find them by name"""
    nova = _get_nova_client(config)
    vms = _find_openstack_vms(nova, config)
    for vm_id in vms:
        vm = nova.servers.get(vm_id)
        snapshot_name = _get_snapshot_name(config, vm.name, tag)
        s = nova.images.find(name=snapshot_name)
        # use findall and check if there is only one, check if s.server.id is
        # the same as the vm.id, check if status is active
        LOG.info("Rebuilding VM '%s' with image '%s'" % (vm.name, s.name))
        vm.rebuild(s)

    for vm_id in vms:
        vm = nova.servers.get(vm_id)
        wait_for("Waiting until VM '%s' is in active state" % vm.name,
                 lambda x: x.status == 'ACTIVE',
                 lambda: nova.servers.get(vm_id),
                 timeout=180)
    # create new ssh connections
    # TODO wait until ssh works, not just an arbitrary sleep
    time.sleep(30)


def delete_openstack_snapshots(config, tag):
    nova = _get_nova_client(config)
    vms = _find_openstack_vms(nova, config)
    for vm_id in vms:
        vm = nova.servers.get(vm_id)
        snapshot_name = _get_snapshot_name(config, vm.name, tag)
        s = nova.images.find(name=snapshot_name)
        LOG.info("Deleting snapshot '%s'" % s.name)
        s.delete()


def _get_nova_client(config):
    manage = config['management']
    nova = client.Client('1.1', manage['user'], manage['password'],
                         manage['tenant'], manage['auth_url'],
                         service_type="compute")
    return nova


def _get_snapshot_name(config, vm_name, tag):
    basename = config['management'].get('snapshot_prefix',
                                        'destroystack-snapshot')
    if tag:
        tag = '_' + tag
    name = "%s_%s%s" % (basename, vm_name, tag)
    return name


def _find_openstack_vms(novaclient, config):
    vms = list()
    for server in config['servers']:
        if 'id' in server:
            vm = novaclient.servers.get(server['id'])
        else:
            vm = _find_openstack_vm_by_ip(novaclient, server['hostname'])

        if vm is None:
            raise Exception("Couldn't find server:\n %s" % server)
        vms.append(vm)
    return vms


def _find_openstack_vm_by_ip(novaclient, ip, vm_id=None):
    all_vms = novaclient.servers.list()
    found = False
    result = None
    for vm in all_vms:
        # ips is a list of lists of IPs for each network
        ip_list = getattr(vm, 'networks', dict()).values()
        # chain the ips into a single level list
        all_ips = list(itertools.chain.from_iterable(ip_list))
        if ip in all_ips:
            if found is True:
                raise Exception("Found two VMs with the IP '%s'. This means it"
                                " is possible for more VMs to have the same IP"
                                " in your setup. To uniquely identify VMs,"
                                " please provide the 'id' field in the"
                                " configuration for each server")
            found = True
            result = vm
    return result
