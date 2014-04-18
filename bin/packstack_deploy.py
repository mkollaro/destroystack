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

from copy import copy
import sys
import logging

import destroystack.tools.common as common
import destroystack.tools.servers as server_tools
from destroystack.tools.server_manager import ServerManager

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

# packages that will be checked for or installed on either localhost or server
# set in --execute_from
REQUIRED_PACKAGES = ['openstack-packstack', 'openstack-utils']

PACKSTACK_DEFAULT_OPTIONS = {
    "CONFIG_GLANCE_INSTALL":            "n",
    "CONFIG_CINDER_INSTALL":            "n",
    "CONFIG_NOVA_INSTALL":              "n",
    "CONFIG_QUANTUM_INSTALL":           "n",
    "CONFIG_NEUTRON_INSTALL":           "n",
    "CONFIG_HORIZON_INSTALL":           "n",
    "CONFIG_SWIFT_INSTALL":             "n",
    "CONFIG_CEILOMETER_INSTALL":        "n",
    "CONFIG_CLIENT_INSTALL":            "y",
    "CONFIG_SWIFT_STORAGE_ZONES":       "1",
    "CONFIG_SWIFT_STORAGE_REPLICAS":    "3",
    "CONFIG_SWIFT_STORAGE_FSTYPE":      "ext4",
    "CONFIG_PROVISION_TEMPEST":         "n",
    "CONFIG_KEYSTONE_ADMIN_PW":         "123456",
    "CONFIG_NOVA_NETWORK_PUBIF":        "eth0",
    "CONFIG_NOVA_COMPUTE_PRIVIF":       "lo",
    "CONFIG_NOVA_NETWORK_PRIVIF":       "lo",
}

OPT_ERROR = "Please use the format 'user:password@server' in  --execute_from"


def main():
    options = _get_options()
    server = _get_server(options)

    install_packages(server, REQUIRED_PACKAGES)

    # TODO: cycle trough common.SUPPORTED_SETUPS and get the func by name
    if options.setup == "swift_small_setup":
        deploy_swift_small_setup(server)
    else:
        print "Unimplemented setup " + options.setup
        sys.exit(1)


def deploy_swift_small_setup(main_server):
    """Install keystone+swift proxy on one server, data servers on other.

    Also formats the extra disks provided to the data servers.
    """
    setup_name = 'swift_small_setup'
    answerfile = "packstack." + setup_name + ".answer"
    config = common.get_config("config." + setup_name + ".json")
    manager = ServerManager(config)

    keystone = manager.get(role='keystone')
    proxy_servers_ip = [s.ip for s in manager.servers(role='swift_proxy')]
    data_servers = list(manager.servers(role='swift_data'))
    data_nodes = server_tools.prepare_extra_disks(data_servers)

    packstack_opt = copy(PACKSTACK_DEFAULT_OPTIONS)
    packstack_opt["CONFIG_SWIFT_INSTALL"] = "y"
    packstack_opt["CONFIG_KEYSTONE_HOST"] = keystone.ip
    packstack_opt["CONFIG_MYSQL_HOST"] = keystone.ip
    packstack_opt["CONFIG_QPID_HOST"] = keystone.ip
    packstack_opt["CONFIG_SWIFT_PROXY_HOSTS"] = ",".join(proxy_servers_ip)
    packstack_opt["CONFIG_NOVA_COMPUTE_HOSTS"] = ",".join(proxy_servers_ip)
    packstack_opt["CONFIG_SWIFT_STORAGE_HOSTS"] = ",".join(data_nodes)
    _create_packstack_answerfile(main_server, packstack_opt, answerfile)

    LOG.info("Running packstack, this may take a while")
    main_server.cmd("packstack --answer-file=%s" % answerfile, log_output=True)
    _configure_keystone(main_server, config["keystone"])


def install_packages(server, packages):
    packages = ' '.join(packages)
    server.cmd('yum install -y %s' % packages, log_output=True)


def _configure_keystone(main_server, config):
    # TODO create the user if it's not admin
    user = config["user"]
    password = config["password"]
    main_server.cmd("source ~/keystonerc_admin && "
                    "keystone user-password-update --pass '%s' %s"
                    % (password, user))
    if user == "admin":
        main_server.cmd("echo 'export OS_PASSWORD=%s' >> ~/keystonerc_admin"
                        % password)
    else:
        # TODO create keystonerc_username
        pass


def _create_packstack_answerfile(main_server, answers, filename):
    main_server.cmd("packstack --gen-answer-file=%s" % filename)
    for question, answer in answers.iteritems():
        main_server.cmd("openstack-config --set %s general %s %s"
                        % (filename, question, answer))


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
        server = server_tools.LocalServer()
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
        server = server_tools.Server(host, user, password)
    server.cmd("uname -a", log_output=True)
    return server


if __name__ == '__main__':
    main()
