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

from nose import SkipTest
from destroystack.tools.server_manager import ServerManager
import destroystack.tools.common as common
import destroystack.tools.tempest as tempest


def requirements(manager):
    return "tempest" in common.CONFIG


class TestRestarts():
    manager = None

    @classmethod
    def setupClass(cls):
        cls.manager = ServerManager(common.CONFIG)
        if not requirements(cls.manager):
            raise SkipTest
        cls.manager.save_state()

    def setUp(self):
        pass

    def tearDown(self):
        self.manager.load_state()

    def test_compute_restart(self):
        compute_server = self.manager.get(role='compute')
        if not compute_server:
            raise SkipTest
        compute_server.cmd("service openstack-nova-compute restart")
        tempest.run(test_type="smoke", include="compute")
