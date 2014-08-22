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

import itertools
import nose

from destroystack.tools.server_manager import ServerManager
from destroystack.tools.swift import Swift
import destroystack.tools.common as common

REPLICA_COUNT = 3


def requirements(manager):
    """Specify requirements for this group of tests to run.

    Return True if at least 2 Swift data servers are present, with at least 6
    disks in total.
    """
    swift_data = manager.get_all(role='swift_data')
    all_disks = list(itertools.chain.from_iterable(
                     [server.disks for server in swift_data]))
    return (len(swift_data) >= 2 and len(all_disks) >= 6)


class TestSwiftSmallSetup():
    swift = None
    manager = None

    @classmethod
    def setupClass(cls):
        cls.manager = ServerManager()
        if not requirements(cls.manager):
            raise nose.SkipTest
        cls.manager.save_state()
        cls.swift = Swift(cls.manager)

    def setUp(self):
        self.data_servers = self.manager.get_all(role='swift_data')
        common.populate_swift_with_random_files(self.swift)
        # make sure all replicas are distributed before we start killing disks
        self.swift.wait_for_replica_regeneration()

    def tearDown(self):
        self.manager.load_state()

    def test_one_disk_down(self):
        self.data_servers[0].kill_disk()
        self.swift.wait_for_replica_regeneration()

    def test_two_disks_down(self):
        self.data_servers[0].kill_disk()
        self.data_servers[1].kill_disk()
        self.swift.wait_for_replica_regeneration()

    def test_one_disk_down_restore(self):
        # kill disk, restore it with all files intact

        disk = self.data_servers[0].kill_disk()
        self.swift.wait_for_replica_regeneration()
        self.data_servers[0].restore_disk(disk)
        # replicas should be on the first 3 nodes (primarily nodes)
        self.swift.wait_for_replica_regeneration(check_nodes=REPLICA_COUNT)
        # wait until the replicas on handoff nodes get deleted
        self.swift.wait_for_replica_regeneration(exact=True)

    def test_disk_replacement(self):
        # similar to 'test_one_disk_down_restore', but formats the disk

        disk = self.data_servers[0].kill_disk()
        self.swift.wait_for_replica_regeneration()
        # the disk died, let's replace it with a new empty one
        self.data_servers[0].format_disk(disk)
        self.data_servers[0].restore_disk(disk)
        # replicas should be on the first 3 nodes (primarily nodes)
        self.swift.wait_for_replica_regeneration(check_nodes=REPLICA_COUNT)
        # wait until the replicas on handoff nodes get deleted
        self.swift.wait_for_replica_regeneration(exact=True)

    def test_two_disks_down_third_later(self):
        self.data_servers[0].kill_disk()
        self.data_servers[1].kill_disk()
        self.swift.wait_for_replica_regeneration()
        self.data_servers[0].kill_disk()
        self.swift.wait_for_replica_regeneration()
