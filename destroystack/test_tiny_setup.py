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


def setup_module():
    global SWIFT
    SWIFT = swift_manager.get_tiny_setup_manager()

def teardown_module():
    common.delete_testfiles()

class TestTinySetup():
    def setUp(self):
        self.server1 = SWIFT.data_servers[0]
        self.server2 = self.server1
        if len(SWIFT.data_servers) > 1:
            self.server2 = SWIFT.data_servers[1]
        common.populate_swift_with_random_files(SWIFT)

    def tearDown(self):
        SWIFT.reset()

    def test_one_disk_down(self):
        self.server1.kill_disk()
        SWIFT.wait_for_replica_regeneration()

    def test_two_disks_down(self):
        self.server1.kill_disk()
        self.server2.kill_disk()
        SWIFT.wait_for_replica_regeneration()
