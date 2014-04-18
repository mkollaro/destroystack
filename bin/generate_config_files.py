#!/usr/bin/env python
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

"""Generate config files for different OpenStack setups from 'etc/config.json'.

To use this, do `$ cp etc/config.json.sample etc/config.json` and edit the
contents to fit your requirements. You should be fine by just editing the
'servers' section. For more info, see the README file.

The generated files are named 'config.<setup_name>.json' and they are simply
copies of the original 'config.json', but have the 'roles' item for each
server, specifying what services will be running on it.
"""

import json
import logging
from os import path
from copy import deepcopy

import destroystack.tools.common as common

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def main():
    general_config = common.get_config()
    generate_config_files(general_config)


def generate_config_files(general_config):
    """Write the config file

    TODO: make this general for all setups, call the correct function by
        searching the namespace
    """
    setup_name = "swift_small_setup"
    new_config = _get_swift_small_setup_config(general_config)
    file_path = path.join(common.CONFIG_DIR, "config." + setup_name + ".json")
    if new_config:
        with open(file_path, 'w') as f:
            json.dump(new_config, f, indent=4)
        LOG.info("Creating config file '%s'" % file_path)
    else:
        LOG.info("Skipping creation of config file for '%s'" % setup_name)


def _get_swift_small_setup_config(general_config):
    """Create configuration for the Swift small setup.

    It requires that there are at least 3 servers and at least 2 of them have
    to have an extra disk (see the 'extra_disks' field). Ideally, they should
    have 3 disks (or 3 partitions), but if you only have one extra disk each,
    it will get formatted it into 3 partitions (not here, later).

    :param conf: Config object
    :returns: copy of the general_config, but with added 'roles' for each
        server, or None if the general configuration doesn't fulfill the
        requirements
    """
    new_config = deepcopy(general_config)
    if len(new_config['servers']) < 3:
        LOG.error("The swift small setup requires at least 3 servers")
        return None
    data_server_count = 0
    proxy_server_count = 0
    for server in new_config['servers']:
        if 'roles' not in server:
            server['roles'] = []

        if _has_extra_disks(server) and data_server_count < 2:
            data_server_count += 1
            server['roles'].append('swift_data')
        elif proxy_server_count == 0:
            proxy_server_count += 1
            server['roles'].append('swift_proxy')
            server['roles'].append('keystone')
    if data_server_count < 2:
        LOG.error("The swift small setup requires at least 2 servers with an"
                  " extra disk or partition")
        return None
    return new_config


def _has_extra_disks(server):
    return ('extra_disks' in server and len(server['extra_disks']) > 0)


if __name__ == '__main__':
    main()
