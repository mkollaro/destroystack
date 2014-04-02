# Frequently Asked Questions

### Why do I need to run the system on VMs?

Restoring the state of the system is necessary after a fault injection, since
the fault might cause other tests to fail. Snapshots are used for this purpose,
and while there are more options on how to do it, this seems to be the simplest
option so far.


### Can I test a system that runs on bare metal with this?

First, *don't ever run these tests on a system you want to keep*, it will
really destroy things on it (format disks, change configuration, restart them,
etc).

That being said, you have multiple options:

1. add support for LVM snapshots
2. do manual restoration of files and databases (very error prone)
3. reinstall the system after each test
4. don't do state restoration and just hope everything works as it should


### Why are snapshots necessary?

The tests need to be isolated - one failed test (or even one that succeeded,
but destroyed something important) might cause all other tests to fail. It
would be possible to restore the changes manually, i.e. backup and copy back
files, mount disks back, start up services again. However, I found this to be
very error prone and tedious and while I might keep the manulal reset for some
tests, it won't be generally supported.

It is possible to turn the state reset off completely, but you might get a lot
of false negatives.


### Why are you using VirtualBox for the demo?

Vagrant is a really nice tool that is currently mainly working with VirtualBox,
but there is a libvirt plugin in development. It saves time - it's easy to use
and later I will have support for both Virtualbox and libvirt (hopefully).


### Why isn't this part of Tempest?

Tempest has a completely different aim. By design, it only uses the APIs of the
services and doesn't have access to the machines directly, therefore it cannot
do things like restart a service.


### Is this only for Swift?

Definitely not. I only started with Swift because it has some built-in HA
features and explicitly focuses on reliability.


### What about HA tests?

Yep, I'm planning some high availability tests. For example, set up a component
in HA and kill one of the nodes. The current problem with this is - we don't
have a proper and stable deployment tool that can set this up yet.


### Can it test multiple topologies?

Yes, every test module is meant for a different topology of OpenStack. Maybe it
will be possible to set up a single topology to rule them all (imagine 15-20
machines if it's supposed to be HA), but there might be conflicts - one test
could require exactly 2 cinder nodes, another might need at least 3. This might
be worked around in some ways though.

There can be multiple ways to run these tests:

1. low resources: set up one topology, run tests for that setup, reinstall into
   new topology, run tests, ...
2. lots of resources: set up a single huge topology that can run all the
   tests (might not be possible)
3. lots of resources, little time: run it in parallel - get machines for each
   topology, install each separately, run only the part of the tests that
   require that setup for each

### Do I have to use Packstack?

No, you can deploy it however you like, the setup just needs to be in sync with
the generated configuration files. Please be so kind and commit a script that
would deploy using an alternative deployment tool, if you have one.
