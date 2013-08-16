#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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

import json
import destroystack.tools.common as common


class ConfigException(Exception):
    pass


class Config(object):
    servers = list()
    keystone = dict()
    setup_tools = dict()
    services_password = ''
    timeout = 0

    def __init__(self):
        self._theconfig = None
        self._load_json()
        self._set_keystone()

    def _load_json(self):
        f = open(common.CONFIG_DIR + "/config.json")
        self._theconfig = json.load(f)
        self.servers = self._theconfig["servers"]
        self.timeout = self._theconfig["timeout"]
        self.timeout = self._theconfig["setup_tools"]
        self.services_password = self._theconfig["services_password"]
        assert self.servers
        assert self.timeout > 0

    def _set_keystone(self):
        self.keystone["server"] = self.servers[0]
        url = "http://" + self.servers[0]["hostname"] + ":5000/v2.0/"
        self.keystone["auth_url"] = url
        self.keystone["username"] = "admin"
        self.keystone["password"] = self.services_password


def get_proxies_or_dataservers(conf,
        combined_count=0, proxy_count=0, dataserver_count=0):
    """ Decide which servers to use as proxies, dataservers or both.

    It will assign the servers with disk first to the dataservers, then to the
    combined servers (which are to be used as both proxy and dataserver) and
    then the rest of them as proxies.

    :param conf: Config object
    :raises ConfigException: if there are less than
        proxy_count+dataserver_count+combined_count servers available in the
        config or if you want more dataservers then there are servers with disks
    :returns: (proxy_list, datacenter_list) where the combined servers will be
        included in both
    """
    if len(conf.servers) < proxy_count + dataserver_count + combined_count:
        raise ConfigException("Not enough servers")
    got_disks = []
    no_disks = []
    for server in conf.servers:
        if "extra_disks" in server and len(server["extra_disks"]) > 0:
            got_disks.append(server)
        else:
            no_disks.append(server)
    if dataserver_count+combined_count > len(got_disks):
        raise ConfigException("Not enough servers with extra disks")

    dataservers = [got_disks.pop() for _ in range(0, dataserver_count)]
    combined = [got_disks.pop() for _ in range(0, combined_count)]
    rest = got_disks + no_disks
    proxies = [rest.pop() for _ in range(0, proxy_count)]
    return (combined + proxies, combined + dataservers)

def get_swift_small_setup_conf(conf):
    """ Decide which servers to use for what depending on available servers

    Use 1 proxy + 2 dataservers if 3 servers are available, improvise otherwise.

    :param conf: Config object
    :returns: (proxy_list, datacenter_list)
    """
    counts = (0, 1, 2) # combined, proxies, datacenters
    if len(conf.servers) == 2:
        counts = (1, 0, 1)
    elif len(conf.servers) == 1:
        counts = (1, 0, 0)
    return get_proxies_or_dataservers(conf, *counts)
