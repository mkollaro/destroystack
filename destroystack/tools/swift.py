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

import swiftclient
import logging
import requests
import time
import destroystack.tools.common as common
from destroystack.tools.timeout import timeout

LOG = logging.getLogger(__name__)
TIMEOUT = common.get_timeout()

# workaround for some DEBUG messages that don't get captured by nose
swiftclient.client.logger.setLevel(logging.INFO)


class Swift(swiftclient.client.Connection):
    """Swift client and extra functionality

    :param server_manager: a ServerManager object, the class uses it to access
        the Swift servers and perform administrative operations; if it doesn't
        contain and servers with the roles 'swift_proxy' or 'swift_data', these
        extra function won't work
    """
    def __init__(self, server_manager):
        auth_url, user, tenant, password = common.get_keystone_auth()
        super(Swift, self).__init__(auth_url, user, password,
                                    auth_version='2', tenant_name=tenant)
        self.manager = server_manager
        self.proxy_server = self.manager.get(role='swift_proxy')

    def replicas_are_ok(self, count=3, check_nodes=None, exact=False):
        """Check if all objects and containers have enough replicas.

        If no replicas of the object or container are left (so they got removed
        completely), this method will not be able to recognize that and will
        return True if all the other data (which were not lost) have enough
        replicas.

        TODO: check account replicas too

        :param check_nodes: Look only at first x number of nodes. Since usually
            the first 'count' nodes are primary nodes, if you set
           'check_nodes=count', no handoff nodes will be checked out. If
            set to None, try all of them.
        :param exact: also fail if there are more than 'count' replicas
        :returns: True iff there are 'count' replicas of everything
        """
        account = self._get_account_hash()
        containers = [c['name'] for c in self.get_account()[1]]

        # check objects
        for container in containers:
            objects = [o['name'] for o in self.get_container(container)[1]]
            for obj in objects:
                urls = self._get_replicas_direct_urls(account, container, obj)
                if not file_urls_ok(urls, "object " + obj, count, check_nodes,
                                    exact):
                    return False

        # check containers
        for container in containers:
            urls = self._get_replicas_direct_urls(account, container)
            if not file_urls_ok(urls, "container " + container, count,
                                check_nodes, exact):
                return False

        LOG.info("all replicas found")
        return True

    @timeout(TIMEOUT, "The replicas were not consistent within timeout.")
    def wait_for_replica_regeneration(self, count=3, check_nodes=None,
                                      exact=False):
        """Wait until there are 'count' replicas of everything.

        :param check_nodes: Look only at first x number of nodes. Since usually
            the first 'count' nodes are primary nodes, if you set
            'check_nodes=count', no handoff nodes will be checked out. If
            set to None, try all of them.
        :param exact: also fail if there are more than 'count' replicas
        :raises TimeoutException: after time in seconds set in the config file
        """
        LOG.info("Waiting until there is the right number of replicas")
        while not self.replicas_are_ok(count, check_nodes, exact):
            time.sleep(5)

    def _get_account_hash(self):
        """Gets the Swift account hash of the currently connected user.

        Note: shouldn't there be a nicer way to do this in swiftclient?
        """
        return self.url.split('/')[-1]

    def _get_replicas_direct_urls(self, account_hash, container_name=None,
                                  object_name=None):
        """Return a tuple of the URLs of replicas.

        The returned URLs are where the account/container/object replicas can
        be directly accessed. The object (or anything else) doesn't actually
        need to exist, it will give you a URL where it would exist if you
        created it.

        The first 'replica_count' (normally set to 3) items returned are
        primarily locations where the data will be unless there was a failure,
        the rest will be handoff nodes where the data will be only if there was
        a failure in the primarily locations (the number of them depends on the
        number of nodes there are).
        """
        ring = ''
        if object_name is not None and container_name is not None:
            ring = "object"
        elif container_name is not None:
            ring = "container"
            object_name = ''
        else:
            ring = "account"
            container_name = ''
            object_name = ''
        cmd = "swift-get-nodes -a /etc/swift/%s.ring.gz %s %s %s |grep curl" \
              % (ring, account_hash, container_name, object_name)
        output = self.proxy_server.cmd(cmd).out
        urls = [line.split('#')[0].split()[-1].strip('" ')
                for line in output]
        return urls


def file_urls_ok(urls, name, count=3, check_url_count=None, exact=False):
    """Go trough URLs of the file and check if at least 'count' responded.

    :param name: for logging output, should be something like "object file123"
    :param count: how many URLs need to be valid
    :param check_url_count: try only first x number of the URLs. If set to
        None, try all.
    :param exact: also fail if there are more than 'count' replicas
    """
    found = 0
    for url in urls[:check_url_count]:
        r = requests.get(url)
        if r.status_code in [200, 204]:
            found += 1
        else:
            LOG.debug("file not found on %s", url)
        if not exact and found == count:
            break
    if found < count:
        LOG.warning("Found only %i copies of '%s'", found, name)
        return False
    elif exact and found > count:
        LOG.warning("Found %i copies of '%s', which is more then should be",
                    found, name)
        return False
    else:
        return True
