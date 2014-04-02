# DestroyStack

**WARNING:** Some of the described features are work in progress, please don't
try to run this yet

**WARNING:** Do not run these on a production system! I will destroy everything
you love.

This project tries to test the reliability of OpenStack by simulating failures,
network problems and generally destroying data and nodes to see if the setup
survives it. The basic idea is to inject some fault, see if everything still
works as expected and restore the state back to what it was before the fault.
Currently contains only Swift tests, but other components are planned.

## Requirements

You will either need access to some VMs running in an OpenStack cloud or
VirtualBox locally. Using VMs is necessary because the machines are being
snapshotted between the tests to provide test isolation and recover from
failures (see [FAQ](FAQ.md)). Support for Amazon AWS and libvirt VMs might be
added in the future.

If you need bare metal, you can add support for LVM snapshotting, or you can
use the manual best-effort recovery (see [FAQ](FAQ.md]).

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


## Running the tested system inside OpenStack VMs

If you have a production instance of OpenStack where you can manage VMs, you
can install OpenStack on them (therefore, run OpenStack inside OpenStack). You
will give the tests access to the meta OpenStack API and IDs of the VMs, so
that it can snapshot them between tests. First, create 3 VMs and either use the
ephemeral flavor or add a cinder disk. (I will hopefully provide a Heat
template and a script to do all this later).

    $ cd destroystack
    $ cp etc/config.json.openstack.sample etc/config.json

Set the VM IDs and links in the config file. Change the disk names in case they
are called differently than `/dev/{vdb,vdc,vdd}`. Don't put your main disk in
here! They will all be
formatted. Just add or remove server entries depending on how many you
have. The services password is what will be set in the answer files for keystone
and other things, you don't need to change it. The timeout is in seconds and
tells the tests how long to wait for stuff like replica regeneration before
failing the tests.

    $ python bin/generate_answerfiles.py


If you chose to use packstack, install Swift like this:

    $ packstack --answer-file=etc/packstack.swiftsmallsetup.answfile

TODO: There will be multiple setups and packstack (or other tool, set in a
configuration file) will be probably run in the module or package setup
function, not manually. There should still remain the possibility to do it
manually - install Swift any way you wish, run a subset of tests that uses that
setup, reinstall Swift, run another subset of tests...

Run the tests:

    $ nosetests

## Running the tested system on bare metal

There are multiple possibilities on how to get this working on bare metal.

1. add support for LVM snapshots
2. do manual restoration of files and databases (very error prone)
3. reinstall the system after each test
4. don't do state restoration and just hope everything works as it should

## General idea

One of the main reasons for Swift (and OpenStack on the whole) to exist is to
create a reliable distributed system. There are specific scenarios which should
be tested, for example a failure of a whole zone, failures of services, network
problems, etc, which require a complex setup.

If you're thinking about adding a test case, ask yourself this: "Does my test
**require** root access to one of the machines?". If no, your test case
probably belongs to [Tempest](https://github.com/openstack/tempest).

Snapshotting is done to provide test isolation, since a single failed test
could fail every other test. I tried reseting back to the original state by
backing up and restoring files, but it proved tedious and error prone.

For more information, read the [test plan](TEST_PLAN.md).
