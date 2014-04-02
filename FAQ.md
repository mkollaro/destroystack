# Frequently Asked Questions

## Why do I need to run the system on VMs?

Restoring the state of the system is neccessary after a fault injection, since
the fault might cause other tests to fail. Snapshots are used for this purpose,
and while there are more options on how to do it, this seems to be the simplest
option so far.


## Can I test a system that runs on bare metal with this?

First, *don't ever run these tests on a system you want to keep*, it will
really destroy things on it (format disks, change configuration, restart them,
etc).

That being said, you have multiple options:

1. add support for LVM snapshots
2. do manual restoration of files and databases (very error prone)
3. reinstall the system after each test
4. don't do state restoration and just hope everything works as it should


## Why are snapshots neccessary?

The tests need to be isolated - one failed test (or even one that succeeded,
but destroyed something important) might cause all other tests to fail. It
would be possible to restore the changes manually, i.e. backup and copy back
files, mount disks back, start up services again. However, I found this to be
very error prone and tedious and while I might keep the manulal reset for some
tests, it won't be generally supported.

It is possible to turn the state reset off completely, but you might get a lot
of false negatives.


## Why are you using VirtualBox for the demo?

Vagrant is a really nice tool that is currently mainly working with VirtualBox,
but there is a libvirt plugin in development. It saves time - it's easy to use
and later I will have support for both Virtualbox and libvirt (hopefully).


## Why isn't this part of Tempest?

Tempest has a completely different aim. By design, it only uses the APIs of the
services and doesn't have access to the machines directly, therefore it cannot
do things like restart a service.
