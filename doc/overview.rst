

Epics PV Archiver Overview
===========================

The Epics PV Archiver saves Epics PVs into a MySQL database and provides a web
interface for looking up, plotting, and managing the archiving process.  The Archiver
can easily accommodate thousands of PVs and save and retrieve data for many years.

The PV Archiver provides Alerts, which will send an email notification when a
particular PV goes out of an acceptable range.  It also provides a concept of an
Instrument, which is a group of PVs for which you may want to save and look
up positions.

Caching and Archiving Processes
---------------------------------

The Epics PV Archiver uses two running processes:

The Caching Process reads the Epics PVs as fast as it can and stores their
    values into a cache database, where other processes can read the "current value".
    Using this cache cuts down on the number of Epics Channel Access connections need
    to be made, and speeds up access to the data values. The caching process also
    manages the email alerts and instruments.

The Archiving Process reads the set of Epics PVs from the cache
    and archives them into a separate database.  Not every change is
    archived, as detailed in the Setup section.

Normally, you do not need to think very much about these two processes
except that they both need to be running.  The <<Setting / Admin page>>
will show the current status of the two processes, including the number of
PVs updated in the cache and the number archived recently. For both of
these, there should be a substantial amount of activity.  See <<Setup
Help>> for more information on managing these processes.

Adding PVs to the Archive
-----------------------------

There are a few ways to add PVs to the archive, all of them very easy.

First, you can use the command line program pvarch, with

   ~> pvarch add_pv MyPV.VAL

You can add multiple PVs on a single line:

   ~> pvarch add_pv MyPV1.VAL  MyPV2.VAL

This will add both PVs, and also set them as "related PVs", which will show
up in the plot view page.

Second, you can put a list of PVs in a file, either one per line or
multiple PV names per line (separated by a space or comma), and run

   ~> pvarch add_pvfile PVList.txt

This is probably most useful on initial setup or when adding a large set of
new PVs.  As with pvarch add_pv, putting multiple PVs on a single
line will make the "Related".

The third way to add PVs is to put them in one of the template files for
the web status pages (See the <<Template>> Page for details).  The next
time the corresponding web page is accessed, the system will see that the
PV is not included, will initially report 'Unknown', and request it to be
added to the Cache and Archive processes.

For all these methods, the PV will not actually be added unless it is a
valid Epics PV that can be accessed from the server.  In some cases, you
may wish to record remote PVs -- you'll want to set EPICS_ADDR_LIST
accordingly.

Adding Motor PVs
~~~~~~~~~~~~~~~~~~~~~

When adding a PV for a Motor (that is, one that has a record type of
'motor' from the Epics Motor Record), all of the following fields will
automatically be added, and all pairs of PVs will be set to be related:

 .VAL   Value
 .DESC   Description
 .OFF   Offset
 .FOFF  Freeze Offset
 .DIR   Direction
 .SET   Set Value
 .HLS   High Limit is Set
 .LLS   Low Limit is Set
 _able.VAL   Motion is Enabled
 .SPMG      Stop/Pause/Move/Go

This subset of all the fields of the motor record are thought to be enough
to reconstruct "where a motor was" and/or "what happened to the alignment
questions".

Related PVs
~~~~~~~~~~~~~

As alluded to above, there is a concept that some PVs can be "related" to
others.  The Archiver uses a simple scoring method for pairs of PVs, and
pairs of PVs that have a non-zero score are said to be related.  In
addition, any time a pair of PVs are plotted together, the score is
increased, so that they will 'move up' in the list of related PVs.

 When PV are added to the archive, pairs of PVs will get an initial pair score
of 10 under the following conditions:

 They are listed on the same command line with pvarch add_pv
 They are listed on the same line of a PV file added with pvarch add_pvfile
 They are listed on the same line of a web template file.
 They are from an Epics Motor.
 They are included together in an Instrument.

The list of related PVs for any PV can also be managed through the Settings
/ Admin page, where you can adjust the score for any pair of PVs.

Web Pages
-------------

Controlling the layout and details of the main Web Status Pages is discussed on the
<<Web Page Template>> Page.


