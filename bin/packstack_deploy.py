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

from socket import gethostbyname
import sys
import logging

import destroystack.tools.common as common
import destroystack.tools.servers as servers

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

PACKSTACK_DEFAULT_OPTIONS = {
    "os-glance-install": "n",
    "os-cinder-install": "n",
    "os-nova-install": "n",
    "os-quantum-install": "n",
    "os-horizon-install": "n",
    "os-swift-install": "n",
    "os-client-install": "y",
    "os-swift-storage-zones": 1,
    "os-swift-storage-replicas": 3,
    "os-swift-storage-fstype": "ext4",
}

OPT_ERROR = "Please use the format 'user:password@server' in  --execute_from"


def main():
    options = _get_options()
    server = _get_server(options)

    # TODO: cycle trough common.SUPPORTED_SETUPS and get the func by name
    if options.setup == "swift_small_setup":
        deploy_swift_small_setup(server)
    else:
        print "Unimplemented setup " + options.setup
        sys.exit(1)


def deploy_swift_small_setup(server):
    """Install keystone+swift proxy on one server, data servers on other.

    Also formats the extra disks provided to the data servers.
    """
    config = common.get_config("config.swift_small_setup.json")
    keystone = _get_ips([config["keystone"]["server"]])
    proxy_servers = _get_ips(config["swift"]["proxy_servers"])
    data_servers = _get_ips(config["swift"]["data_servers"])
    data_nodes = _get_swift_storage_nodes(config["swift"]["data_servers"])
    hosts = keystone
    hosts.extend(data_servers)

    _format_extra_disks(config["swift"]["data_servers"])

    packstack_opt = PACKSTACK_DEFAULT_OPTIONS
    packstack_opt["install-hosts"] = ",".join(hosts)
    packstack_opt["os-swift-install"] = "y"
    packstack_opt["keystone-host"] = keystone[0]
    packstack_opt["os-swift-proxy"] = ",".join(proxy_servers)
    packstack_opt["os-swift-storage"] = ",".join(data_nodes)

    LOG.info("Running packstack, this may take a while")
    server.cmd("packstack %s"
               % _get_packstack_opts(packstack_opt), log_output=True)
    _configure_keystone(server, config["keystone"])


def _configure_keystone(server, config):
    # TODO create the user if it's not admin
    user = config["user"]
    password = config["password"]
    server.cmd("source ~/keystonerc_admin && "
               "keystone user-password-update --pass '%s' %s"
               % (password, user))
    if user == "admin":
        server.cmd("echo 'export OS_PASSWORD=%s' >> ~/keystonerc_admin"
                   % password)
    else:
        # TODO create keystonerc_username
        pass


def _get_packstack_opts(opts):
    """Take a dict of packstack options and make a string out of them.

    For example, opts["os_swift_install"]='y' will become
    "--os_swift_install=y".
    """
    return " ".join(["--%s=%s" % (key, value) for key, value in opts.items()])


def _get_options():
    parser = common.get_option_parser()
    parser.add_option("-e", "--execute-from", dest="execute_from",
                      help="URI of server from which to run packstack, "
                           "in the format 'user:password@server'.",
                      default="localhost")
    options, _ = parser.parse_args()
    return options


def _get_server(options):
    """Get the Server or LocalServer from which to execute Packstack.

    If execute-from is set to localhost, return LocalServer. If it is set to a
    URI in the format 'user:pass@server', it will create an SSH connection to
    it.
    """
    server = None
    if options.execute_from == "localhost":
        server = servers.LocalServer()
    else:
        if '@' not in options.execute_from:
            print OPT_ERROR
            sys.exit(1)
        user, host = options.execute_from.split('@', 1)
        password = None
        if ':' in user:
            user, password = user.split(':', 1)
        if not user or not host:
            print OPT_ERROR
            sys.exit(1)
        server = servers.Server(host, user, password)
    server.cmd("uname -a", log_output=True)
    return server


def _get_swift_storage_nodes(dataserver_configs):
    """ Return a list in form ["ip.address/vda", "ip.address.2/vda"]
    """
    storage = list()
    for server in dataserver_configs:
        for disk in server['extra_disks']:
            ip = gethostbyname(server["hostname"])
            storage.append(ip + "/" + disk)
    return storage


def _format_extra_disks(data_servers_config):
    for config in data_servers_config:
        LOG.info("Formatting extra disks on %s" % config["hostname"])
        server = servers.Server(**config)
        server.format_extra_disks()


def _get_ips(config):
    return [gethostbyname(s["hostname"]) for s in config]


if __name__ == '__main__':
    main()
