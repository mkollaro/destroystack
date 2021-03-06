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
6. copy the configuration file (you don't have to edit it)

        $ cp etc/config.json.vagrant.sample etc/config.json
7. copy the OpenStack RPM repository to the VMs if necessary
8. deploy the system using Packstack (but you can use a different tool)

        $ python bin/packstack_deploy.py
9. run tests

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
where you can manage VMs, you can install the tested system on them -
run OpenStack inside OpenStack.
The steps you need to take are similar to the steps used with VirtualBox,
except in step 5 you need to create the virtual machines yourself. For
the basic set of Swift tests, create three VMs and either use the ephemeral
flavor or add a Cinder disk. You can try using the
[Khaleesi](https://github.com/redhat-openstack/khaleesi) project for this
purpose.
Another difference is the configuration file, in which you will need to
give the tests access to the meta OpenStack API and edit the IP addresses
of the servers.

    $ cp etc/config.json.openstack.sample etc/config.json

Configure the `management` section to point to your meta-OpenStack
system endpoint, user name and password. If your meta-OpenStack uses
unique IPs for the VMs, you can just use those, but if not you need to
provide the IDs of the VMs under the `id` field. Change the disk names
in case they are called differently than `/dev/{vdb,vdc,vdd}`. There is a
workaround for the case when you have only one extra disk - three partitions
will be created on it, so you can use a single one and the tools will detect
it. All the disks will be wiped and formatted. The services password
is what will be set in the answer files for keystone and other things, you
don't need to change it. The timeout is in seconds and tells the tests how
long to wait for stuff like replica regeneration before failing the tests. For
more information about the configuration file, look at `etc/schema.json`
which is a JSON schema of it and can serve as a validation tool.

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
