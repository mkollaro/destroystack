
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

"""Save and restore the state of the system with Vagrant.

Expects that `VAGRANT_DIR`, which is usually just the project root directory,
is expected to contain a Vagrant file which specifies the VMs that should be
used. The module expects that the VMs are already running and will
create/restore/delete the snapshots of all of them.
"""

import logging
from time import sleep
import destroystack.tools.common as common
from destroystack.tools.servers import LocalServer

LOG = logging.getLogger(__name__)
CONFIG = common.get_config()

# directory which contains the Vagrantfile
VAGRANT_DIR = common.PROJ_DIR


def create_snapshots(tag=''):
    """Create snapshots of all Vagrant VMs found in the `VAGRANT_DIR`.

    The name of the snapshot will be the snapshot_prefix (defined in the
    configuration file under the 'management' key) + VM name + tag
    Doesn't create new snapshots if the VM already has a snapshot with that
    name.
    :param tag: appended to the name of the snapshot
    """
    vms = _get_vagrant_vms()
    localhost = LocalServer()
    for vm_name in vms:
        snapshot_name = _get_snapshot_name(vm_name, tag)
        if not _snapshot_exists(vm_name, snapshot_name):
            LOG.info("Creating new snapshot of VM '%s'", vm_name)
            localhost.cmd("cd '%s' && vagrant snapshot take %s %s"
                          % (VAGRANT_DIR, vm_name, snapshot_name))
        else:
            LOG.info("Snapshot of VM '%s' with the name '%s' already exists",
                     vm_name, snapshot_name)


def restore_snapshots(tag=''):
    """Restore all the VMs found in `VAGRANT_DIR` to their snapshots.

    Supposed to run after `create_snapshots`.
    The snapshots are found by name, which is the same as in
    `create_snapshots`.

    :param tag: added to the end of the searched name of the snapshot
    """
    vms = _get_vagrant_vms()
    localhost = LocalServer()
    for vm_name in vms:
        snapshot_name = _get_snapshot_name(vm_name, tag)
        if not _snapshot_exists(vm_name, snapshot_name):
            raise Exception("No snapshot with name '%s' found of VM '%s'"
                            % (snapshot_name, vm_name))
        LOG.info("Restoring VM '%s' to  snapshot '%s'", vm_name, snapshot_name)
        localhost.cmd("cd '%s' && vagrant snapshot go %s %s"
                      % (VAGRANT_DIR, vm_name, snapshot_name))
    sleep(3)


def delete_snapshots(tag=''):
    """Delete snapshots of VMS found in `VAGRANT_DIR`.

    The VMs are found by their name, same as in `create_snapshots`. Does not
    fail if some snapshot is not found and deletes the ones that get found.

    Warning: slow operation
    :param tag: added to the end of the searched name of the snapshot
    """
    vms = _get_vagrant_vms()
    localhost = LocalServer()
    for vm_name in vms:
        snapshot_name = _get_snapshot_name(vm_name, tag)
        if _snapshot_exists(vm_name, snapshot_name):
            LOG.info("Deleting snapshot '%s' of VM '%s'",
                     snapshot_name, vm_name)
            localhost.cmd("cd '%s' && vagrant snapshot delete %s %s"
                          % (VAGRANT_DIR, vm_name, snapshot_name))
        else:
            LOG.warning("VM '%s' doesn't have a snapshot with the name '%s'",
                        vm_name, snapshot_name)


def _get_vagrant_vms():
    """Return a list of existing Vagrant VMs names"""
    localhost = LocalServer()
    result = localhost.cmd("cd '%s' && vagrant status| tail -n+3"
                           % VAGRANT_DIR, log_output=False)
    vms = result.out
    # remove the info message after the empty line
    empty_line = vms.index('')
    vms = vms[:empty_line]
    vm_names = [vm.split()[0] for vm in vms]
    LOG.info("Found Vagrant VMs: %s", vm_names)
    return vm_names


def _get_snapshot_name(vm_name, tag):
    basename = CONFIG['management'].get('snapshot_prefix',
                                        'destroystack-snapshot')
    if tag:
        tag = '_' + tag
    name = "%s_%s%s" % (basename, vm_name, tag)
    return name


def _snapshot_exists(vm_name, snapshot_name):
    localhost = LocalServer()
    result = localhost.cmd("cd '%s' && vagrant snapshot list %s| grep %s"
                           % (VAGRANT_DIR, vm_name, snapshot_name),
                           ignore_failures=True,
                           log_cmd=False, log_output=False)
    return bool(result.out)
