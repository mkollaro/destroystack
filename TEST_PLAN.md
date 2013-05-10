# Test Plan for Fail Injection Testing of OpenStack Swift

General assumptions:
* there should be a time limit (~1 minute) for waiting until replica
  regeneration (3 replicas of everything), otherwise the test fails
* replica count is 3 unless stated otherwise
* Swift populated with some random objects and containers

## Tiny Setup

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
    - wait if it gets used again as the primary location and the offhand replica
      gets removed

* 1 disk down, erase and restore it (disk replacement)
    - force umount disk, run mkfs on it
    - wait until replica regeneration
    - mount the disk back
    - wait if it gets used again as the primary location and the offhand replica
      gets removed

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
      locations for the data, but it should still be available from offhand
      disks)

* [expected failure] 3 disks down
    - umount 3 disks at the same time (1 on server #1, others on server #2)
    - check if it fails gracefully (some data will get lost, but other should be
      still available)
    - wait until the replica count of data not lost is 3 again, check whether a
      user accessing the lost data gets a meaningful error message
    - as user, access data that did not get lost

* shutdown one data server, wait, start it again
    - force shutdown data server #1
    - note: servers are usually down only for a few minutes, so Swift doesn't
      start the replication of all it's disks immediately, which would cause a
      lot of sudden (and probably unnecessary) traffic; look at how exactly this
      is expected to work and perhaps set the wait time between failure and
      replication to something lower so it can be tested in reasonable time
    - another note: what happens if a server fails right in the middle of
      request response?
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


## Medium Setup


    +-----------------+
    | Proxy Server #1 +-----+
    |                 |     |
    +-----------------+     |
    +-----------------+     |
    | Proxy Server #2 +-----+
    |                 |     |
    +-----------------+     |
                            |
      +----------+----------+
      |          |          |
    +-+------+ +-+------+ +-+------+
    | Data   | | Data   | | Data   |
    | Server | | Server | | Server |
    | #1     | | #2     | | #3     |
    |        | |        | |        |
    +--------+ +--------+ +--------+

Assumptions:
* account server on data server #1, container server on #2, object server on #3

Notes:
* a separate server for keystone?

Tests:
* shutdown one proxy server, wait, start it again
    - force shutdown  proxy server #1
    - as user, upload and download some files
    - start proxy server #1
    - as user, upload and download some files
    - check if the proxy service is running on both proxies

* TODO


## Large Setup

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

Notes:
* is this a realistic scenario?
* how should keystone be put into this? A keystone server in each region would
  be the most realistic way (I suppose), but then problems in keystone could
  make Swift tests fail
* would this scenario make sense with zones instead of regions? Do zones get
  used like this?
* what about replication in this scenario? How long does a region wait until
  deciding it should start replication? what happens after this time period?
  doesn't it cause a mass replication that would make Swift unresponsive?

Tests:
* network partition between regions
    - "cut the cable" between regions (for example, set the firewall to block
      everything)
    - make users near region #1 update some files
    - check if updates were written
    - make users near region #2 update some files
    - check if updates were written
    - note: is it possible for 2 users to write into the same file? if yes, how
      does it get merged if they each made it in a different region?
    - "connect the cable" between regions again
    - see if the updates were distributed between the regions, wait until
      everything is consistent

* TODO somehow check if the closer proxy gets used (proxy affinity)


## Ideas

* disk and server failures during rebalances
* change configuration files, restart servers
* packet dropping and big latency
* randomly stop or restart Swift services
