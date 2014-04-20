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

# packages that will be checked for on local host
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


def main():
    option_parser = common.get_option_parser()
    options, _ = option_parser.parse_args()

    server = server_tools.LocalServer()
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
    _set_swift_mount_check(data_servers)


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


def _set_swift_mount_check(data_servers):
    """Set the parameter mount_check to True in /etc/swift/*-server.conf

    If this is not checked True, Swift will replicate files onto the
    system disk if the disk is umounted.
    """
    for server in data_servers:
        server.cmd("""
            sed -i -e 's/mount_check.*=.*false/mount_check = true/' \
            /etc/swift/*-server.conf""")
    for server in data_servers:
        server.cmd("swift-init account container object rest restart")


if __name__ == '__main__':
    main()
