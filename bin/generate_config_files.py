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
"""

import json
import logging
from os import path

import destroystack.tools.common as common

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def main():
    general_config = common.get_config()
    generate_swift_small_setup_config(general_config)


def generate_swift_small_setup_config(general_config):
    """Write the config file"""
    filename = "config.swift_small_setup.json"
    swift_small_config = _get_swift_small_setup_config(general_config)
    with open(path.join(common.CONFIG_DIR, filename), 'w') as f:
        json.dump(swift_small_config, f, indent=4)
    LOG.info("Config file for the Swift small setup:\n%s",
             json.dumps(swift_small_config, indent=4))


def _get_commands(tools, options):
    """Set the module and test setup/teardown commands based on setup_tools."""
    cmd = dict()
    cmd["module_setup"] = ""
    cmd["module_teardown"] = ""
    cmd["test_setup"] = ""
    cmd["test_teardown"] = ""

    def get_path(script):
        return path.join(common.BIN_DIR, script)

    if tools["setup_script"]:
        cmd["module_setup"] = '%s %s' \
            % (get_path(tools["setup_script"]), options)
    if tools["cleanup_script"]:
        cmd["module_teardown"] = '%s %s' \
            % (get_path(tools["cleanup_script"]), options)
    if tools["save_state_script"]:
        cmd["test_setup"] = '%s %s' \
            % (get_path(tools["save_state_script"]), options)
    if tools["load_state_script"]:
        cmd["test_teardown"] = '%s %s' \
            % (get_path(tools["load_state_script"]), options)
    return cmd


def _get_swift_small_setup_config(general_config):
    """Create configuration for the Swift small setup.

    Decide which servers to use for what depending on available servers.  Use 1
    proxy + 2 dataservers if 3 servers are available, improvise otherwise.

    :param conf: Config object
    :returns: (proxy_list, datacenter_list)
    """
    servers = general_config["servers"]
    counts = (0, 1, 2)  # combined, proxies, datacenters
    msg = "Swift small setup tests. You may experience problems, \
           3 servers are recommended."
    if len(servers) == 2:
        LOG.warn("Using only two servers for %s" % msg)
        counts = (1, 0, 1)
    elif len(servers) == 1:
        LOG.warn("Using only one server for %s" % msg)
        counts = (1, 0, 0)

    new_config = dict()
    new_config["swift"] = _get_swift_servers(servers, *counts)

    k = new_config["swift"]["proxy_servers"][0]
    new_config["keystone"] = _get_keystone(k, general_config["keystone"])
    tools = general_config["setup_tools"]
    new_config["commands"] = _get_commands(tools, "--setup=swift_small")
    return new_config


def _get_keystone(server, keystone_conf):
    """
    :param server: a dict with the keystone server info, like
        {"hostname":"abc.com", "root_password":"123"}
    :param keystone_conf: a dict with keystone settings
        {"user":"admin", "password":"123456"}
    """
    result = dict()
    url = "http://" + server["hostname"] + ":5000/v2.0/"
    result["server"] = server
    result["auth_url"] = url
    result["user"] = keystone_conf["user"]
    result["password"] = keystone_conf["password"]
    return result


def _get_swift_servers(servers,
                       combined_count=0, proxy_count=0, dataserver_count=0):
    """Decide which servers to use as proxies, dataservers or both.

    It will assign the servers with disk first to the dataservers, then to the
    combined servers (which are to be used as both proxy and dataserver) and
    then the rest of them as proxies.

    :param servers: list of servers. A server should have an "extra_disks" item
        to be used as a data center (or combined)
    :raises ConfigException: if there are less than
        proxy_count+dataserver_count+combined_count servers available in the
        config or if you want more dataservers then there are servers with
        disks
    :returns: (proxy_list, datacenter_list) where the combined servers will be
        included in both
    """
    if len(servers) < proxy_count + dataserver_count + combined_count:
        raise common.ConfigException("Not enough servers in config file")
    got_disks = []
    no_disks = []
    for server in servers:
        if "extra_disks" in server and len(server["extra_disks"]) > 0:
            got_disks.append(server)
        else:
            no_disks.append(server)
    if dataserver_count + combined_count > len(got_disks):
        raise common.ConfigException("Not enough servers with extra disks")

    dataservers = [got_disks.pop() for _ in range(dataserver_count)]
    combined = [got_disks.pop() for _ in range(combined_count)]
    rest = got_disks + no_disks
    proxies = [rest.pop() for _ in range(proxy_count)]
    return {"proxy_servers": combined + proxies,
            "data_servers": combined + dataservers}


if __name__ == '__main__':
    main()
