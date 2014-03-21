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

import destroystack.tools.swift_manager as swift_manager
import destroystack.tools.common as common

SWIFT = None
CONFIG = None
REPLICA_COUNT = 3


def setup_module():
    global SWIFT
    global CONFIG
    CONFIG = common.get_config("config.swift_small_setup.json")
    SWIFT = swift_manager.SwiftManager(CONFIG)


def teardown_module():
    pass


class TestSwiftSmallSetup():
    def setUp(self):
        self.server1 = SWIFT.data_servers[0]
        self.server2 = self.server1
        if len(SWIFT.data_servers) > 1:
            self.server2 = SWIFT.data_servers[1]
        common.populate_swift_with_random_files(SWIFT)
        # make sure all replicas are distributed before we start killing disks
        SWIFT.wait_for_replica_regeneration()

    def tearDown(self):
        SWIFT.reset()

    def test_one_disk_down(self):
        self.server1.kill_disk()
        SWIFT.wait_for_replica_regeneration()

    def test_two_disks_down(self):
        self.server1.kill_disk()
        self.server2.kill_disk()
        SWIFT.wait_for_replica_regeneration()

    def test_one_disk_down_restore(self):
        # kill disk, restore it with all files intact

        disk = self.server1.kill_disk()
        SWIFT.wait_for_replica_regeneration()
        self.server1.restore_disk(disk)
        # replicas should be on the first 3 nodes (primarily nodes)
        SWIFT.wait_for_replica_regeneration(check_nodes=REPLICA_COUNT)
        # wait until the replicas on handoff nodes get deleted
        SWIFT.wait_for_replica_regeneration(exact=True)

    def test_disk_replacement(self):
        # similar to 'test_one_disk_down_restore', but formats the disk

        disk = self.server1.kill_disk()
        SWIFT.wait_for_replica_regeneration()
        # the disk died, let's replace it with a new empty one
        self.server1.format_disk(disk)
        self.server1.restore_disk(disk)
        # replicas should be on the first 3 nodes (primarily nodes)
        SWIFT.wait_for_replica_regeneration(check_nodes=REPLICA_COUNT)
        # wait until the replicas on handoff nodes get deleted
        SWIFT.wait_for_replica_regeneration(exact=True)

    def test_two_disks_down_third_later(self):
        self.server1.kill_disk()
        self.server2.kill_disk()
        SWIFT.wait_for_replica_regeneration()
        self.server1.kill_disk()
        SWIFT.wait_for_replica_regeneration()
