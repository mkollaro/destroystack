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

import os
import random
import string

PROJ_DIR = os.path.join(os.path.dirname(__file__), "..")
TESTFILE_DIR = os.path.join(PROJ_DIR, "test_files")


def upload_files(swift, container, filename_list):
    """ Upload files from the TESTFILE_DIR.

    Creates the container if it doesn't exist.
    """
    swift.put_container(container)
    for filename in filename_list:
        f = open(os.path.join(TESTFILE_DIR, filename))
        swift.put_object(container, filename, f)

def populate_swift_with_random_files(swift, prefix='',
                                    container_count=5, files_per_container=5):
    """ Create random files in test_files dir and upload them to Swift.

    :param prefix: prefix before container and file names
    :param container_count: how many containers to create
    :param files_per_container: how many files to upload per container
    """
    containers = [prefix + "container" + str(i)
                    for i in range(0, container_count)]
    files = [prefix + "file" + str(i) + ".txt"
                    for i in range(0, container_count*files_per_container)]
    for filename in files:
        f = open(os.path.join(TESTFILE_DIR, filename), 'w')
        f.write(random_string()+'\n')
        f.close()
    start = 0
    for container in containers:
        upload_files(swift, container, files[start:start+files_per_container])
        start += files_per_container

def delete_testfiles(prefix=''):
    """ Delete all *.txt file in test_files directory

    :param prefix: only delete files starting with prefix
    """
    os.chdir(TESTFILE_DIR)
    for f in os.listdir("."):
        if f.endswith(".txt") and f.startswith(prefix):
            os.remove(f)

def random_string(min_lenght=1, max_length=20):
    """ Generate random string made out of alphanumeric characters. """
    length = random.randint(min_lenght, max_length)
    chars = string.ascii_letters + string.digits

    return ''.join([random.choice(chars) for _ in range(length)])