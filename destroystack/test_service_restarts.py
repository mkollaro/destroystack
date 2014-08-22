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

import nose
import destroystack.tools.server_manager as server_manager
import destroystack.tools.common as common
import destroystack.tools.tempest as tempest


class TestRestarts():
    manager = None

    @classmethod
    def setupClass(cls):
        cls.manager = server_manager.ServerManager()
        if "tempest" not in common.CONFIG:
            raise nose.SkipTest("Tempest required to verify service restarts")
        cls.manager.save_state()

    @classmethod
    def teardownClass(cls):
        # do the state restoration only once per this group, since they are not
        # particularly damaging to the system
        # TODO(mkollaro) also run it when a test fails
        cls.manager.load_state()

    def test_nova_compute_restart(self):
        server = self.manager.get(role='compute')
        if not server:
            raise nose.SkipTest("Compute role needed for compute service test")
        server.cmd("service openstack-nova-compute restart")
        tempest.run(test_type="smoke", include="compute.servers")

    def test_nova_network_restart(self):
        server = self.manager.get(role='controller')
        if not server:
            raise nose.SkipTest("Compute role needed for compute service test")
        res = server.cmd("service openstack-nova-network status",
                         ignore_failures=True)
        if res.exit_code == 1:  # maybe neutron is being used
            raise nose.SkipTest("Service nova-network doesn't seem to exist")
        tempest.run(test_type="smoke", include="network")

    def test_keystone_restart(self):
        server = self.manager.get(role='keystone')
        if not server:
            raise nose.SkipTest("Keystone role needed for eystone test")
        server.cmd("service openstack-keystone restart")
        tempest.run(test_type="smoke", include="identity")

    def test_swift_proxy_restart(self):
        server = self.manager.get(role='swift_proxy')
        if not server:
            raise nose.SkipTest("Swift_proxy role needed for swift test")
        server.cmd("service openstack-swift-proxy restart")
        tempest.run(test_type="smoke", include="object_storage")
