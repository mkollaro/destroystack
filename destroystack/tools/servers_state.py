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
import itertools
from novaclient import client
from destroystack.tools.timeout import wait_for

LOG = logging.getLogger(__name__)


def save(config, tag=''):
    _choose_action(config, 'save', tag)


def load(config, tag=''):
    _choose_action(config, 'load', tag)


def delete(config, tag=''):
    _choose_action(config, 'delete', tag)


def _choose_action(config, action, tag):
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

    for snapshot_id in snapshots:
        snapshot = nova.images.get(snapshot_id)
        wait_for("Waiting until snapshot '%s' is active" % snapshot.name,
                 lambda x: x.status == 'ACTIVE',
                 lambda: nova.images.get(snapshot_id))


def load_openstack_snapshots(config, tag):
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
                 lambda: nova.servers.get(vm_id))
        # TODO wait until ssh works
        # create new ssh connections


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
