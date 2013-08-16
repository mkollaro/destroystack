# DestroyStack

This project tries to test the reliability of OpenStack Swift by simulating
failures, network problems and generally destroying data and nodes to see if the
setup survives it. Currently specializes only on Swift, but later it could do
fail injection tests on other OpenStack projects.


## Requirements

Should be run using 3 testing servers, but can be tried out on a single server
too. The servers should have 6 extra empty disks in total - a good setup should
be 1 server without extra disks, 2nd server with 3 extra disk, 3rd server with
another 3 disks. The extra disks should have a file system and no partitions.
Their size is not important - 1 GB per disk is enough. The servers can be
virtual machines, there is no need for bare metal, and should be running RHEL
(Fedora not tested yet) and have a yum repository that contains OpenStack
packages. Your SSH keys have to be distributed on them. For more info on the
setups, see the file `TEST_PLAN.md`

You may need [packstack](https://github.com/stackforge/packstack) (but you can
use some other installation tool) and `python-nose` on the machine from which
you run the tests (do not run them on the test machines).

Future requirements will be around 6 testing servers.

## Usage

    $ cd destroystack
    $ cp etc/config.json.sample etc/config.json

Replace `SERVERx.COM` with the host names of your servers in the `config.json`
file. Change the disk names in case they are called differently than
`/dev/{vdb,vdc,vdd}`. Don't put your main disk in here! They will all be
formatted. You can use a single server for the basic tests, but you will need at
least 6 disks on it. Just add or remove server entries depending on how many you
have. The services password is what will be set in the answer files for keystone
and other things, you don't need to change it. The timeout is in seconds and
tells the tests how long to wait for stuff like replica regeneration before
failing the tests.

    $ python destroystack/tools/generate_answerfiles.py

If you want to use something different for Swift installation, look into the
answer files in `etc/` and make sure you will use the exact same topology as
written on top of the file. Even using more servers than DestroyStack chose to
use may cause false positives.

If you chose to use packstack, install Swift like this:

    $ packstack --answer-file=etc/packstack.swiftsmallsetup.answfile

TODO: There will be multiple setups and packstack (or other tool, set in a
configuration file) will be probably run in the module or package setup
function, not manually. There should still remain the possibility to do it
manually - install Swift any way you wish, run a subset of tests that uses that
setup, reinstall Swift, run another subset of tests...

Run the tests:

    $ nosetests


## General idea

One of the main reasons for Swift (and OpenStack on the whole) to exist is to
create a reliable distributed system. There are specific scenarios which should
be tested, for example a failure of a whole zone, failures of services, network
problems, etc, which require a complex setup.

If you're thinking about adding a test case, ask yourself this: "Does it really
require more than a single machine setup?". If no, your test case probably
belongs to [tempest](https://github.com/openstack/tempest) or into the tests
that are part of Swift's source code.

The Swift deployment gets reset after each test case - right now it is done by
making a backup of the `*.ring.gz` and `*.builder` files (among others) in the
beginning and then restoring them after each test case and restarting the
services. This could also be done with packstack, but it is slow (which could
perhaps be fixed). Another option would be to to use snapshots of the test
machines.

For more information, read the `TEST_PLAN.md` file.
