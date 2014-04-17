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
from novaclient import exceptions
from destroystack.tools.timeout import wait_for
from destroystack.tools.servers import Server as SshServer
import destroystack.tools.common as common

LOG = logging.getLogger(__name__)
SNAPSHOT_TIMEOUT = 5*60
CONFIG = common.get_config()


def save(tag=''):
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
    _choose_action('save', tag)


def load(tag=''):
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
    _choose_action('load', tag)


def delete(tag=''):
    """Delete all the snapshots of the servers.

    For more information, see the function ``save``.

    Depending on what is in the configuration in "management.type":
        * manual - Do nothing (removing the backup files is not implemented)
        * none - Do nothing
        * openstack - Remove all the snapshots with the names as described in
            the ``save`` function
    """
    _choose_action('delete', tag)


def _choose_action(action, tag):
    """Choose which function to use, based on "management.type" in config.

    :param action: save, load or delete
    """
    if 'management' not in CONFIG or 'type' not in CONFIG['management']:
        raise Exception("The management type has to be in config")
    assert action in ['save', 'load', 'delete']

    type = CONFIG['management']['type']
    if type == 'openstack':
        if action == 'save':
            create_openstack_snapshots(tag)
        elif action == 'load':
            load_openstack_snapshots(tag)
        else:
            delete_openstack_snapshots(tag)
    elif type == 'vagrant':
        raise NotImplementedError("vagrant snapshots are not implemented yet")
    elif type == 'manual':
        raise NotImplementedError("to be done very soon")
    elif type == 'none':
        LOG.info("State save and restoration has been turned off")
    else:
        raise Exception("This type of server management, '%s', is not"
                        "supported" % type)


def create_openstack_snapshots(tag):
    """Create snapshots of OpenStack VMs and wait until they are active.
    """
    nova = _get_nova_client()
    vms, ssh_servers = _find_openstack_vms(nova)

    snapshots = list()
    for vm_id, ssh in zip(vms, ssh_servers):
        vm = nova.servers.get(vm_id)
        snapshot_name = _get_snapshot_name(vm.name, tag)
        s = _find_snapshot(nova, snapshot_name)
        if s:
            LOG.warning("Snapshot '%s' already exist, re-using it"
                        % snapshot_name)
            snapshots.append(s)
        else:
            # let things settle a bit
            time.sleep(3)
            # sync the file system first
            ssh.cmd("sync")
            LOG.info("Creating snapshot '%s'" % snapshot_name)
            s = vm.create_image(snapshot_name)
            snapshots.append(s)

    for snapshot_id in snapshots:
        snapshot = nova.images.get(snapshot_id)
        wait_for("Waiting until snapshot '%s' is active" % snapshot.name,
                 lambda x: x.status == 'ACTIVE',
                 lambda: nova.images.get(snapshot_id),
                 timeout=SNAPSHOT_TIMEOUT)


def load_openstack_snapshots(tag):
    """Restore snapshots of servers - find them by name"""
    nova = _get_nova_client()
    vms, _ = _find_openstack_vms(nova)
    for vm_id in vms:
        vm = nova.servers.get(vm_id)
        snapshot_name = _get_snapshot_name(vm.name, tag)
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
                 timeout=SNAPSHOT_TIMEOUT)
    # create new ssh connections
    # TODO wait until ssh works, not just an arbitrary sleep
    time.sleep(3*60)


def delete_openstack_snapshots(tag):
    nova = _get_nova_client()
    vms, _ = _find_openstack_vms(nova)
    for vm_id in vms:
        vm = nova.servers.get(vm_id)
        snapshot_name = _get_snapshot_name(vm.name, tag)
        s = nova.images.find(name=snapshot_name)
        LOG.info("Deleting snapshot '%s'" % s.name)
        s.delete()


def _find_snapshot(novaclient, snapshot_name):
    try:
        snapshot = novaclient.images.find(name=snapshot_name)
        return snapshot
    except exceptions.NotFound:
        return None


def _get_nova_client():
    manage = CONFIG['management']
    nova = client.Client('1.1', manage['user'], manage['password'],
                         manage['tenant'], manage['auth_url'],
                         service_type="compute")
    return nova


def _get_snapshot_name(vm_name, tag):
    basename = CONFIG['management'].get('snapshot_prefix',
                                        'destroystack-snapshot')
    if tag:
        tag = '_' + tag
    name = "%s_%s%s" % (basename, vm_name, tag)
    return name


def _find_openstack_vms(novaclient):
    vms = list()
    ssh_servers = list()
    for server in CONFIG['servers']:
        if 'id' in server:
            vm = novaclient.servers.get(server['id'])
        else:
            vm = _find_openstack_vm_by_ip(novaclient, server['hostname'])

        if vm is None:
            raise Exception("Couldn't find server:\n %s" % server)
        ssh = SshServer(**server)
        vms.append(vm)
        ssh_servers.append(ssh)
    return vms, ssh_servers


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
