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
import logging

import destroystack.tools.common as common
import destroystack.tools.servers as server_tools
from destroystack.tools.server_manager import ServerManager

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
logging.getLogger("paramiko").setLevel(logging.WARNING)

# packages that will be checked for on local host
REQUIRED_PACKAGES = ['openstack-packstack', 'openstack-utils',
                     'python-novaclient']

PACKSTACK_DEFAULT_OPTIONS = {
    "CONFIG_GLANCE_INSTALL":            "n",
    "CONFIG_CINDER_INSTALL":            "n",
    "CONFIG_NOVA_INSTALL":              "n",
    "CONFIG_QUANTUM_INSTALL":           "n",
    "CONFIG_NEUTRON_INSTALL":           "n",
    "CONFIG_HORIZON_INSTALL":           "n",
    "CONFIG_SWIFT_INSTALL":             "n",
    "CONFIG_CEILOMETER_INSTALL":        "n",
    "CONFIG_NAGIOS_INSTALL":            "n",
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

# packstack answerfile that will be created locally
ANSWERFILE = 'packstack.answer'


def main():
    server = server_tools.LocalServer()
    install_packages(server, REQUIRED_PACKAGES)

    create_configuration(server)
    deploy(server)


def install_packages(server, packages):
    packages = ' '.join(packages)
    server.cmd('yum install -y %s' % packages, log_output=True)


def create_configuration(main_server):
    """Using the server roles in the config file, create a packstack answerfile

    """
    packstack_answers = copy(PACKSTACK_DEFAULT_OPTIONS)
    config = common.get_config()
    manager = ServerManager(config)
    _configure_roles(packstack_answers, manager)
    _configure_swift(packstack_answers, manager)
    _configure_remaining_roles(packstack_answers, manager)
    _create_packstack_answerfile(main_server, packstack_answers, ANSWERFILE)


def deploy(main_server):
    """Run Packstack and configure components if necessary
    """
    config = common.get_config()
    manager = ServerManager(config)
    LOG.info("Running packstack, this may take a while")
    main_server.cmd("packstack --answer-file=%s" % ANSWERFILE,
                    collect_stdout=False)
    _configure_keystone(main_server, config["keystone"])

    data_servers = list(manager.servers(role='swift_data'))
    _set_swift_mount_check(data_servers)


def get_ips(host_list):
    """Return string 'address,address,address' from IPs in the host list"""
    return ','.join([x.ip for x in host_list])


def _configure_roles(packstack_opt, manager):
    keystone = manager.get_all(role='keystone')
    if keystone:
        packstack_opt["CONFIG_KEYSTONE_HOST"] = get_ips(keystone)


def _configure_swift(packstack_opt, manager):
    """Add Swift proxy/data servers to packstack answerfile.

    Also formats the extra disks provided to the data servers.
    """

    proxy_servers = manager.servers(role='swift_proxy')
    data_servers = list(manager.servers(role='swift_data'))
    if not (proxy_servers and data_servers):
        return

    data_nodes = server_tools.prepare_swift_disks(data_servers)
    packstack_opt["CONFIG_SWIFT_INSTALL"] = "y"
    packstack_opt["CONFIG_SWIFT_PROXY_HOSTS"] = get_ips(proxy_servers)
    packstack_opt["CONFIG_SWIFT_STORAGE_HOSTS"] = ",".join(data_nodes)


def _configure_remaining_roles(packstack_opt, manager):
    """Configure neccessary services if they haven't been configured yet

    If services like the database or messaging queue haven't been configured so
    far, set them to use the controller (of if that is not available, use the
    keystone host...or just pick any of the hosts if even that wasn't
    specified)
    """
    controller = manager.get(role='controller')
    keystone = manager.get(role='keystone')

    # server on which to install remaining services
    general_server = controller or keystone or manager.get()

    for service in ["CONFIG_KEYSTONE_HOST",
                    "CONFIG_MYSQL_HOST",
                    "CONFIG_QPID_HOST"]:
        if service not in packstack_opt:
            packstack_opt[service] = general_server


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
    if not main_server.file_exists(filename):
        main_server.cmd("packstack --gen-answer-file=%s" % filename)
    else:
        LOG.info("Reusing existing packstack answer file")
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
