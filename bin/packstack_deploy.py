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

# local server object on which packstack will be run
LOCALHOST = None

# packages that will be checked for on local host
REQUIRED_PACKAGES = ['openstack-packstack', 'openstack-utils',
                     'python-novaclient']

# password that will be set to services (like database)
DEFAULT_SERVICE_PASS = "123456"

PACKSTACK_DEFAULT_OPTIONS = {
    "CONFIG_GLANCE_INSTALL": "n",
    "CONFIG_CINDER_INSTALL": "n",
    "CONFIG_NOVA_INSTALL": "n",
    "CONFIG_QUANTUM_INSTALL": "n",
    "CONFIG_NEUTRON_INSTALL": "n",
    "CONFIG_HORIZON_INSTALL": "n",
    "CONFIG_SWIFT_INSTALL": "n",
    "CONFIG_CEILOMETER_INSTALL": "n",
    "CONFIG_NAGIOS_INSTALL": "n",
    "CONFIG_CLIENT_INSTALL": "y",
    "CONFIG_SWIFT_STORAGE_ZONES": "1",
    "CONFIG_SWIFT_STORAGE_REPLICAS": "3",
    "CONFIG_SWIFT_STORAGE_FSTYPE": "ext4",
    "CONFIG_PROVISION_TEMPEST": "n",
    "CONFIG_PROVISION_DEMO": "n",
    "CONFIG_KEYSTONE_ADMIN_PW": DEFAULT_SERVICE_PASS,
    "CONFIG_NOVA_NETWORK_PUBIF": "eth0",
    "CONFIG_NOVA_COMPUTE_PRIVIF": "lo",
    "CONFIG_NOVA_NETWORK_PRIVIF": "lo",
}

# packstack answerfile that will be created locally
ANSWERFILE = 'packstack.answer'


def main():
    global LOCALHOST
    LOCALHOST = server_tools.LocalServer()
    install_packages(REQUIRED_PACKAGES)

    create_configuration()
    deploy()


def install_packages(packages):
    packages = ' '.join(packages)
    LOCALHOST.cmd('yum install -y %s' % packages, log_output=True)


def create_configuration():
    """Using the server roles in the config file, create a packstack answerfile

    """
    packstack_answers = copy(PACKSTACK_DEFAULT_OPTIONS)
    manager = ServerManager()
    _configure_roles(packstack_answers, manager)
    _configure_keystone(packstack_answers, manager)
    _configure_swift(packstack_answers, manager)
    _create_packstack_answerfile(packstack_answers)


def deploy():
    """Run Packstack and configure components if necessary
    """
    manager = ServerManager()
    LOG.info("Running packstack, this may take a while")
    LOCALHOST.cmd("packstack --answer-file=%s" % ANSWERFILE,
                  collect_stdout=False)

    data_servers = list(manager.servers(role='swift_data'))
    _set_swift_mount_check(data_servers)
    _set_iptables(manager)


def get_ips(host_list):
    """Return string 'address,address,address' from IPs in the host list"""
    return ','.join([x.ip for x in host_list])


def _configure_roles(packstack_opt, manager):
    compute = manager.get_all(role='compute')
    if compute:
        packstack_opt["CONFIG_COMPUTE_HOSTS"] = get_ips(compute)
        packstack_opt["CONFIG_NOVA_COMPUTE_HOSTS"] = get_ips(compute)
        packstack_opt["CONFIG_NOVA_INSTALL"] = "y"
        packstack_opt["CONFIG_GLANCE_INSTALL"] = "y"
        packstack_opt["CONFIG_CINDER_INSTALL"] = "y"


def _configure_keystone(packstack_opt, manager):
    keystone = manager.get_all(role='keystone')
    if keystone:
        packstack_opt["CONFIG_KEYSTONE_HOST"] = get_ips(keystone)

    user = common.CONFIG["keystone"].get("user", "admin")
    if user != "admin":
        raise Exception("This helper script assumes that you are using the"
                        " 'admin' keystone user")
    password = common.CONFIG["keystone"].get("password", DEFAULT_SERVICE_PASS)
    packstack_opt["CONFIG_KEYSTONE_ADMIN_PW"] = password


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


def _get_default_host():
    """Get one of the hosts that will be defaultly used by services.

    This is usually the host with the role 'controller' (one of them is
    selected), but if there is no such role specified, use the 'keystone' role.
    If even that is unavailable, just choose the first host provided.
    """
    manager = ServerManager()
    controller = manager.get(role='controller')
    keystone = manager.get(role='keystone')

    return controller or keystone or manager.get()


def _set_default_host_in_answerfile():
    """Set all the hosts in the answerfile to the default host (controller).

    Packstack by default creates an answerfile that uses localhost for all
    services, but since we usually run Packstack from a separate server that
    isn't supposed to have OpenStack installed, it is better to choose one from
    the servers given in the config. The exception is the server on which
    OpenStack clients should be installed, which will remain the same
    (localhost).
    """
    # save the original host to which OpenStack clients should be installed
    res = LOCALHOST.cmd(
        "openstack-config --get %s general CONFIG_OSCLIENT_HOST" % ANSWERFILE)
    original_client_host = ''.join(res.out)
    default_host = _get_default_host().ip
    LOCALHOST.cmd("sed -ri 's/HOST(S?)\w*=.*/HOST\\1=%s/' %s"
                  % (default_host, ANSWERFILE))
    # restore host for client installation
    LOCALHOST.cmd("openstack-config --set %s general CONFIG_OSCLIENT_HOST %s"
                  % (ANSWERFILE, original_client_host))


def _create_packstack_answerfile(answers):
    if not LOCALHOST.file_exists(ANSWERFILE):
        LOCALHOST.cmd("packstack --gen-answer-file=%s" % ANSWERFILE)
        _set_default_host_in_answerfile()
    else:
        LOG.info("Reusing existing packstack answer file")
    for question, answer in answers.iteritems():
        LOCALHOST.cmd("openstack-config --set %s general %s %s"
                      % (ANSWERFILE, question, answer))


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


def _set_iptables(manager):
    """Allow all incoming traffic to the OpenStack nodes from local IP"""
    ip = _get_localhost_ip()
    if not ip:
        # since this functionality might not be necessary, just give up
        return

    for server in manager.get_all():
        server.cmd("iptables -I INPUT -s %s -j ACCEPT" % ip)
        server.cmd("service iptables save")


def _get_localhost_ip():
    return ''.join(LOCALHOST.cmd("hostname --ip-address").out)


if __name__ == '__main__':
    main()
