# Test Plan

## Nova

    +-----------+    +--------------+
    |Controller +--+-+  Compute #1  |
    +-----------+  | |              |
                   | +--------------+
                   |
                   | +--------------+
                   +-+  Compute #2  |
                     |              |
                     +--------------+

Assumptions:
* no VMs should be running on either of them in the beginning


Tests:
* kill compute node service
    - stop some of the basic nova services on one of the compute nodes
    - create some VMs
    - check if VMs were scheduled to be created on the other compute node and
      work

* (idea) kill connection to the user
    - assuming there is a private and public network, shut down the public
      interface of one of the compute nodes
    - the node is now accessible from the controller, but not from the user -
      what should the nova scheduler do? Is it expected to notice this?
    - in this scenario, the user would get a VM but wouldn't be able to connect
      to it and remove the VM - but if Nova doesn't recognize it,
      it will continue scheduling all his VMs onto this compute node

## Swift

General assumptions:
* there should be a time limit (~1 minute) for waiting until replica
  regeneration (3 replicas of everything), otherwise the test fails
* replica count is 3 unless stated otherwise
* Swift populated with some random objects and containers

### Small Swift Setup

            +-------------------+
            |   Proxy Server    |
            |                   |
            +----------+--------+
                       |
              +--------+---------+
    +---------+------+   +-------+---------+
    | Data Server #1 |   | Data Server #2  |
    |                |   |                 |
    |+-+ +-+ +-+     |   |+-+ +-+ +-+      |
    || | | | | |     |   || | | | | |      |
    || | | | | |     |   || | | | | |      |
    |+-+ +-+ +-+     |   |+-+ +-+ +-+      |
    +----------------+   +-----------------+

Assumptions:
* at least 6 disks in total, 3 on one server and 3 on the other

Tests:
* [smoke] 1 disk down
    - force umount disk
    - wait until replica count is 3 again

* 1 disk down, restore it
    - force umount disk
    - wait until replica count is 3
    - mount the disk back
    - wait until all 3 primary nodes have a replica and no offhand node has one
      (there shouldn't be 4 replicas of anything)

* disk replacement (1 disk down, erase and restore it)
    - force umount disk, run mkfs on it
    - wait until replica regeneration
    - mount the disk back
    - wait until all 3 primary nodes have a replica and no offhand node has one
      (there shouldn't be 4 replicas of anything)

* [smoke] 2 disks down
    - umount 2 disks at the same time (one on data server #1, the second on
      server #2)
    - wait for replica regeneration

* 2 disks down, wait, 3rd disk down
    - umount 2 disks at the same time (one on data server #1, the second on
      server #2)
    - wait until replica count is at least 2 again
    - umount a 3rd disk
    - wait until replica regeneration
    - check if objects are accessible by users (now there are no primary
      locations for some of the data, but they should still be available from
      offhand disks)

* [expected failure] 3 disks down
    - umount 3 disks at the same time (1 on server #1, others on server #2)
    - check if it fails gracefully (some data will get lost, but other should
      be still available)
    - wait until the replica count of data not lost is 3 again, check whether a
      user accessing the lost data gets a meaningful error message
    - as user, access data that did not get lost

* restart one data server
    - restart data server #1
    - as user, download some files while the server is restarting, there should
      be no problem
    - replication should not start because of this (servers are usually down
      only for a few minutes, so Swift doesn't start the replication of all
      it's disks immediately, which would cause a lot of sudden (and probably
      unnecessary) traffic)
    - after dataserver #1 started up, check if all required services are
      running

* [expected failure] restart one data server while downloading files
    - upload some big files
    - start downloading them
    - restart data server #1 while files are still being downloaded
    - (?)

* shutdown one data server, wait, start it again
    - force shutdown data server #1
    - note: since there is no general way to wake up a computer after x
      minutes, we could simulate this by using iptables to block all traffic
      (except ssh) and restart it after the given waiting time
    - note: servers are usually down only for a few minutes, so Swift doesn't
      start the replication of all it's disks immediately, which would cause a
      lot of sudden (and probably unnecessary) traffic; look at how exactly this
      is expected to work and perhaps set the wait time between failure and
      replication to something lower so it can be tested in reasonable time
    - wait for replica regeneration

* [expected failure] shutdown proxy server, wait, start it again
    - force shutdown the proxy server
    - try to download or upload some files as a user, log error message
    - start proxy server again
    - download or upload some files as user
    - check if all services are running

* full disk
    - fill the disk with some random data (trough SSH, not with Swift)
    - user uploads some files that have that disk as a primary location
    - object should be put on an offhand node (?)

* almost full disk
    - fill the disk with some random data (trough ssh, not with Swift) so that
      only 1 MB of space is left
    - upload file bigger than 1 MB (somehow make sure that the disk is its
      primary location or upload more files)
    - note: somewhere, there should be an error 507, not enough space, unable to
      fallocate
    - object should be put on an offhand node (?)

* 3 full disks
    - fill 3 disks with some random data (trough ssh, not with Swift)
    - user uploads some files that have those disks as primary locations (note:
      how to make sure of this?)
    - object should be put on an offhand node (?)

* write conflict
    - create 2 users, give them both rights to write into a certain container
    - both users write into the same file at the same moment (maybe repeat this
      with hundreds of files to trigger a race condition)
    - one of the writes should succeed (the one that came in slightly later)
    - check if the replicas are always consistent (all 3 of them have the same
      content at all times)

### Medium Swift Setup

    +-----------------+          +-----------+
    | Proxy Server #1 +-----+----+ Keystone  |
    |                 |     |    |           |
    +-----------------+     |    +-----------+
    +-----------------+     |
    | Proxy Server #2 +-----+
    |                 |     |
    +-----------------+     |
              +-------------+----+
              |                  |
    +---------+------+   +-------+---------+
    | Data Server #1 |   | Data Server #2  |
    |                |   |                 |
    |+-+ +-+ +-+     |   |+-+              |
    || | | | | |     |   || |              |
    || | | | | |     |   || |              |
    |+-+ +-+ +-+     |   |+-+              |
    +----------------+   +-----------------+

Assumptions:
* 3 disks on data server #1, 1 disk on data server #2
* data server #2 has two extra disks that haven't been added to Swift yet

Notes:
* this will probably require some load balancer too
* TODO: have look at haproxy

Tests:
* restart one proxy server
    - force restart  proxy server #1
    - as user, upload and download some files while it is restarting
    - after proxy server #1 started, upload and download some files
    - check if the proxy service is running on both proxies

* restart first proxy server, wait until it started, restart the other proxy
    - force restart  proxy server #1
    - as user, upload and download some files while it is restarting
    - after proxy server #1 started, force restart proxy server #2
    - as user, upload and download some files while it is restarting

* ring builder
    - copy the .buider files to the extra server that runs keystone
    - on the keystone server, add the two extra unconfigured disks to the
      builder files and remove one disk on data server #1 from it
    - as user, start downloading and uploading some random big files
      simultaneously and a few hundred smaller files sequentially
    - while files are still being uploaded/downloaded, start rebalancing the
      nodes (from the keystone server) and copy the ring files to the proxy
      servers
    - all uploads and downloads should have been successful

TODO: failures during rebalancing


### Large Swift Setup

     +----------+                                        +----------+
     | Users    |                                        |    Users |
     +---+------+                                        +-------+--+
         |                                                       |
         |                                                       |
    +----+---------------------+          +----------------------+----+
    |        REGION #1         |          |         REGION #2         |
    |         +------------+   |          |  +-----------+            |
    |         |  Proxy #1  |   +----------+  | Proxy #2  |            |
    |         |            |   |          |  |           |            |
    |         +---------+--+   |          |  +--+--------+            |
    |                   |      |          |     |                     |
    | +------------+    |      |          |     |      +------------+ |
    | |Data Server +----+      |          |     +------+Data Server | |
    | +------------+    |      |          |            +------------+ |
    | +------------+    |      |          |                           |
    | |Data Server +----+      |          |                           |
    | +------------+           |          |                           |
    +--------------------------+          +---------------------------+

Assumptions:
* there is a single connection between the regions (imagine a single cable
  between buildings with the data centers)
* some imaginary users live near region #1 and the others near region #2
  (user1 around region #1 and user2 around region #2)

Notes:
* Is this a realistic scenario?
* How should keystone be put into this? A keystone server in each region would
  be the most realistic way (I suppose), but then problems in keystone could
  make Swift tests fail
* What about replication in this scenario? How long does a region wait until
  deciding it should start replication? What happens after this time period?
  Doesn't it cause a mass replication that would make Swift unresponsive?

Tests:
* network partition between regions
    - "cut the cable" between regions (for example, set the firewall to block
      everything)
    - make user1 update some files
    - check if updates were written
    - make user2 update some files
    - check if updates were written
    - create a write conflict - user1 and user2 write into the same file (user2
      just slightly later)
    - "connect the cable" between regions again
    - see if the updates were distributed between the regions, wait until
      everything is consistent
    - in the write conflict, check if the last change got written (by user2)

* time zones
    - set a different time zone in one of the regions
    - try if the normal operations work (upload/download some files, kill a
      disk and see if replication works,..)
    - create a write conflict between user1 and user2 (they write to the same
      file), user2 slightly later (~1s later)
    - check if user2's update got written
    - repeat the same, but user1 will do a write slightly later and his update
      should win

* proxy affinity
    - try downloading files as user1, they should all be downloaded from a
      data server in region #1 (note: how to make sure of that?)
    - repeat the same for user2, it should get downloaded from region #2



## Ideas

* disk and server failures during rebalances
* change configuration files, restart servers
* packet dropping and big latency
* randomly stop or restart Swift services
