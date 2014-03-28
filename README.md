# DestroyStack

This project tries to test the reliability of OpenStack by simulating
failures, network problems and generally destroying data and nodes to see if the
setup survives it. Currently contains only Swift tests, but other components
are planned.

## Requirements

You will either need access to some VMs running in an OpenStack cloud or
VirtualBox locally. Using VMs is necessary because the machines are being
snapshotted between the tests to provide test isolation and recover from
failures (see FAQ). Support for Amazon AWS and libvirt VMs might be added in
the future.

If you need bare metal, you can add support for LVM snapshotting, or you can
use the manual best-effort recovery (see FAQ).

The tests don't tend to be computationally intensive. For now, you should be
fine if you can spare 2GB of memory for the VMs in total. Certain topologies
need extra disks for Swift, but their size isn't important - 1GB is enough per
disk.

I've only tried these with RHEL and Fedora, plus RDO Havana or RHOS-4.0,
installed by [Packstack](https://github.com/stackforge/packstack). The tests
themselves don't really care what or how is it deployed. For more info on the
setups, see the file `TEST_PLAN.md`. The tests use the `python-nose` framework
and the OpenStack clients, both of which will be installed as dependencies if
you install this repository with pip.


## Demo using VirtualBox

You can try out the demo with Vagrant and VirtualBox (libvirt may be added
later). While easier to use, it isn't fast - creating the virtual machines will
take a few minutes, installing OpenStack on them another 15 minutes and the
tests themselves take a while to run.

    # install the latest version of Vagrant and Virtualbox
    $ pip install -e --user destroystack/
    $ cd destroystack/
    $ vagrant plugin install vagrant-vbox-snapshot
    $ vagrant up
    $ ./demo/run

This will boot up 3 Fedora VMs in VirtualBox, deploy the basic topology for
most DestroyStack tests (others might take more resources than this), create a
snapshot and run the basic tests that are able to run on this topology. Between
the test runs, the snapshot will be restored to provide test isolation.

To remove the VMs and extra files, run

  $ cd destroystack/
  $ vagrant destroy
  $ rm -r tmp/


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
