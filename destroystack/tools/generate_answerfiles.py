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

""" Generate packstack answer files for different setups based on config file.
"""

from os.path import join, expanduser
from socket import gethostbyname
import destroystack.tools.common as common
import destroystack.tools.config as config

def _get_storage_nodes(dataserver_configs):
    """ Return a list in form "some.ip.address/vda,some.other.ip.address/vdb"
    """
    storage = list()
    for server in dataserver_configs:
        for disk in server['extra_disks']:
            ip = gethostbyname(server["hostname"])
            storage.append(ip + "/" + disk)
    return ",".join(storage)

def main():
    """ Generate answer files for packstack
    """
    path = join(common.PROJ_DIR, "..", "etc", "packstack.tinysetup.answfile")
    conf = config.Config()
    proxy_conf, data_conf = config.get_tiny_setup_conf(conf)
    main_ip = gethostbyname(proxy_conf[0]["hostname"])
    nodes = _get_storage_nodes(data_conf)
    with open(path, 'w') as out:
        for line in open(path + ".sample"):
            line = line.replace("MAINSERVER", main_ip)
            line = line.replace("MYPASS", conf.services_password)
            line = line.replace("HOMEPATH", expanduser("~"))
            if "CONFIG_SWIFT_STORAGE_HOSTS" in line:
                line = "CONFIG_SWIFT_STORAGE_HOSTS = " + nodes
            out.write(line)

if __name__ == '__main__':
    main()
