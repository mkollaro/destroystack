Handle the state restoration of server.

Since destroystack injects failures into the tested system, there has to be
some isolation between tests, otherwise a failure caused by one test might
cause an unwanted failure in the next one.

This module can save and restore the state by various methods.  The type of
state restoration is decided in the configuration, "management.type", which can
be:
    * manual
    * none
    * openstack
    * vagrant (not implemented)
    * vagrant-libvirt (not implemented)
    * lvm (not implemented)

The basic one is of type 'manual' - it just backs up some files and restores
them after the tests, plus starts up the services that were turned off and
similar. It's just a best effort restoration - it takes a lot of work to get it
working properly and is not supported for everything. Try not to rely on it if
possible.

The better way is to use snapshots, although this requires that the servers are
VMs. Right now, only snapshots of OpenStack VMs is supported, but VirtualBox
(trough vagrant) and libvirt might get supported in the future. For bare metal,
using the LVM snapshots might get supported.
