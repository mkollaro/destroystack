# DestroyStack

**WARNING:** Do not run these on a production system! I will destroy everything
you love.

This project tries to test the reliability of OpenStack by simulating failures,
network problems and generally destroying data and nodes to see if the setup
survives it. The basic idea is to inject some fault, see if everything still
works as expected and restore the state back to what it was before the fault.
Currently contains only Swift tests, but other components are planned.

## Requirements

You will either need access to some VMs running in an OpenStack cloud or
VirtualBox locally (script for setting them up VirtualBox VMs is already
provided). Using VMs is necessary because the machines are being
snapshotted between the tests to provide test isolation and recover from
failures (see [FAQ](FAQ.md)). Support for Amazon AWS and libvirt VMs might be
added in the future.

If you need bare metal, you can add support for LVM snapshotting, or you can
use the manual best-effort recovery (see [FAQ](FAQ.md)).

The tests don't tend to be computationally intensive. For now, you should be
fine if you can spare 2GB of memory for the VMs in total. Certain topologies
need extra disks for Swift, but their size isn't important - 1GB is enough per
disk.

I've only tried these with RHEL and Fedora, plus RDO Havana or RHOS-4.0,
installed by [Packstack](https://github.com/stackforge/packstack). The tests
themselves don't really care what or how is it deployed. For more info on the
setups, see the [test plan](TEST_PLAN.md). The tests use the `python-nose`
framework and the OpenStack clients, both of which will be installed as
dependencies if you install this repository with pip.


## Demo using VirtualBox

You can try out the demo with Vagrant and VirtualBox (libvirt may be added
later). While easier to use, it isn't fast - creating the virtual machines will
take a few minutes, installing OpenStack on them another 15 minutes and the
tests themselves take a while to run.

1. install the latest version of
   [Vagrant](http://www.vagrantup.com/downloads.html) and
   [Virtualbox](https://www.virtualbox.org/wiki/Downloads)
2. install Vagrant plugin for creating snapshots

        $ vagrant plugin install vagrant-vbox-snapshot
3. install DestroyStack pip dependencies

        $ sudo pip install -e --user destroystack/
4. change to the main destroystack directory (necessary for Vagrant)

        $ cd destroystack/
5. boot up the VirtualBox VMs

        $ vagrant up
6. deploy the demonstration OpenStack system

        $ bin/deploy_demo
7. run tests

        $ nosetests

This will boot up 3 Fedora VMs in VirtualBox, deploy the basic topology for
most DestroyStack tests (others might take more resources than this), create a
snapshot and run the basic tests that are able to run on this topology. Between
the test runs, the snapshot will be restored to provide test isolation.

To remove the VMs and extra files, run

    $ cd destroystack/
    $ vagrant destroy
    $ rm -r tmp/


## Running the tested system inside OpenStack VMs

If you have a production instance of OpenStack (let us call it meta-OpenStack)
where you can manage VMs, you can install OpenStack on them (therefore, run
OpenStack inside OpenStack). You will give the tests access to the meta
OpenStack API and IDs of the VMs, so that it can snapshot them between tests.
First, create 3 VMs and either use the ephemeral flavor or add a cinder disk.
You can try using [khaleesi](https://github.com/redhat-openstack/khaleesi) for
this purpose.

    $ sudo pip install -e --user destroystack/
    $ cd destroystack
    $ cp etc/config.json.openstack.sample etc/config.json

Configure the `management` section to point to your meta-OpenStack system
endpoint, user name and password. If your meta-OpenStack uses unique IPs for
the VMs, you can just put those in configuration, but if not you need to
provide the IDs of the VMs under the `id` field.  Change the disk names in case
they are called differently than `/dev/{vdb,vdc,vdd}`. Don't put your main disk
in here! They will all be formatted. The services password is what will be set
in the answer files for keystone and other things, you don't need to change it.
The timeout is in seconds and tells the tests how long to wait for stuff like
replica regeneration before failing the tests.

    $ python bin/generate_config_files.py

If you chose to use packstack, install the basic topology with this (more will
be supported later):

    $ python bin/packstack_deploy.py --setup=swift_small_setup

Run the tests:

    $ nosetests

## Running the tested system on bare metal

There are multiple possibilities on how to get this working on bare metal.

1. add support for LVM snapshots
2. do manual restoration of files and databases (very error prone)
3. reinstall the system after each test
4. don't do state restoration and just hope everything works as it should

## About the tests

Read the [test plan](TEST_PLAN.md). It's mostly about Swift for now, but more
will be added later - hopefully some HA tests too.

If you're thinking about adding a test case, ask yourself this: "Does my test
**require** root access to one of the machines?". If no, your test case
probably belongs to [Tempest](https://github.com/openstack/tempest).
