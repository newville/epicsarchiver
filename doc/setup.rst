
Epics PV Archiver Setup and Management
========================================

This page gives a few details for setting up and managing the Epics PV
Archiver system.   Installation instructions are in the source kit.

As described in the Overview, the Epics PV Archiver has two main data
stores for PV data, each controlled by a separate running process on the
server:

The Caching Process maintains a cache table of current values for all all
Epics PVs.  This manages all Epics connections, and runs as fast as
possible, but stores only the most recent value for any PV.  This cache is
used by all other processes, including dynamic web pages and the archiving
process.  The caching process is also responsible for sending emails for
Alerts.  The main point of the cache is to allow different processes to get
current values of Epics PVs without having to make an actual Channel Access
connection.

 The Archiving Process stores data for PVs into archives for later
retrieval.  This works by reading recent changes from the cache, and
storing these changes into data tables.  Since many PVs change by a small
amount rather frequently, parameters can be set to limit the number of
changes recorded.

Both processes will write log files to the log directory.

The command-line pvarch process
-----------------------------------

The main administrative interface to the PV Archiver is the command line
program pvarch.  Typical usages of this program are:

Command Meaning
 Status / General Information 

pvarch -h         shows a status message. 
pvarch status     shows cache and archiving status, some recent statistics. 
pvarch check      print # of archived PVs in past 10 minutes. Should be >1! 
pvarch list       prints a list of recent data archives 
pvarch save       create backup files of recent data archives 
pvarch clean      clean out old files in the web data directory

 The Archiving Process 
pvarch start        start the archiving process 
pvarch stop         stop the archiving process 
pvarch restart      restart the archiving process 
pvarch next         restart with 'next run' of data archives   

 The Caching Process 
pvarch cache start        start cache process (if it's not already running) 
pvarch cache stop         stop  cache process 
pvarch cache restart      restart cache process 
pvarch cache status       show # of PVs cached in past 60 seconds  
pvarch cache activity     show list of PVs cached in past 60 seconds 

 Adding and removing PVs 
pvarch add_pv         add a PV to the cache and archive 
pvarch add_pvfile     read a file of PVs to add to the Archiver 
pvarch drop_pv        remove a PV from cache and archive 

Deadtime and Deadbands: setting how often a PV is recorded
-----------------------------------------------------------

While the caching process saves current values for all PVs as fast as it
can, it is not necessary to store all changes to PVs.  Two parameters set
how often values are archived: the deadtime, and the deadband.  Both of
these can be set for each PV.

The deadtime for a PV sets how long to wait after archiving a PVs value
before archiving another value for this PV.  Let's take as an example a
deadtime of 10 seconds.  If the PV hasn't changed in longer than 10
seconds, then a change to the value will be archived as quickly as
possible.  But if the value changes again within 10 seconds, the change
will not be recorded immediately.  Instead, the change will be seen and the
archiver will wait until 10 seconds has elapsed since the last time the
value was recorded.  This way, if multiple changes happen during that 10
seconds, the only value recorded will be the one held after 10 seconds has
elapsed -- all intermediate changes will be forgotten.

 One thing to note, though, is that the time of the last change will be
recorded properly.  Thus, if a value changes, changes again 1 second later,
and then stays fixed, the archiver will record the changes as taking place
1 second apart.

The deadband for a PV sets how big a fractional change must be in
order to be archived.

When PVs are added to the database, typical deadtimes are one or a few
seconds, depending on whether the PV has a type 'double' -- which can
easily change trivial amounts -- or a type of 'int','enum', or 'string',
which change less often.  For this setup, the default deadtime for PVs of
type 'double' or 'float' is 5 seconds, while the default
deadtime for all other PVs is 1 seconds.  Typical
deadbands are set small enough to be not actually effective.

Rotating databases, cron jobs
------------------------------

The archiving process writes data to a single database (more details on
database layout is below).  It is expected and encouraged to have several
of these archive databases, each one representing a 'run' for a fixed time
duration, typically around a weeks to a month.  

 That is, you will want to periodically start archiving into a new
database.  Using pvarch next will tell the Archiver to make the
"next" database in the series of archives and to start collecting into that
new database.  All PVs archived and all their settings in the old database
will be moved into the new one. Using pvarch list will show a list
of the most recent 'runs'.

 Looking up a PV's value for plotting or data retrieval will seamlessly
span multiple databases, so you don't have to worry about how often you
start a new run.  Because of this, putting pvarch next in a cron
table to run once a week or once a month, or at some other frequency, is
recommended.  I would not recommend using a new database more often than
once a day -- once a month or every few weeks seems about right.

 Also, because both pvarch start and pvarch cache
start will do nothing if there is a successfully running archiving and
caching process, you can also put these two commands in cron tables,
running more often to ensure that the caching and archiving are running.

Another potential use of a cron job can be to clean out the data files
created for the data plotting and viewing.  These are temporary files
stored under the apache 'cgi-data' directory.  To clean old files in this
directory, you can use the command

pvarch clean

 Finally, to backup the databases with simple mysql dump files, use
pvarch save.  This will save the two principle databases: the
master database, pvarch_master, and the currently active archive database.
You can specify additional databases to save as command-line arguments:

pvarch save pvdata_00001

Example crontab files for these tasks are included in the source distribution.

Database layout
-------------------

This Epics PV Archiver has two main databases that it uses.  The main or
master database, named pvarch_master, holds the cache of values, status
information about running processes, the history of archive 'runs',
settings for Instruments and Alerts, and the data for related PVs.  The
archive database holds the archived values for the PVs as well as data
about how to archive the data.

At any one time, one archive database is 'current', meaning that it is the
one be written to, so the database in use is a sequentially number
database, of the form pvdata_00001, pvdata_00002, ....  Each databases holds a
set of data for a specific time period -- a 'run'. Data retrieval uses the
full set of archive databases, and looks up older spanning archive
databases as necessary.

 The assumption is that the Python programming interface will be used to
access data in the PV Archive.  While the data is stored with MySQL
databases, using simple SQL queries to retrieve data from the PV Archive is
slightly non-trivial.  Still, for completeness, a partial description of
the databases is provided here:

** Structure of the Master Database:

The master database, pvarch_master, is a fairly simply database.  There are
several tables, but none of them is very complicated, and the logic that
joins them is fairly simple.  The tables are:

 Table         Description  [data columns] , notes
 cache         holds the cached data for all PVs.

	       [id, pvname,type, value, cvalue, ts, active]

               cvalue is the 'character string value',
               ts is the timestamp, active holds whether
               the PV is actively cached.

 runs          holds info about archiving 'runs'. 

               [id, db,notes, start_time, stop_time]

               db is the name of the current archive databases.
               info status information about running 'cache' and 'archive'
               processes id, process, status, db, datetime, ts, pid
               process is either 'cache' or 'archive'.

 requests      temporary storage for requested changes to the cache database

               [id, pvname, action]

               action is 'add', 'drop', 'suspend', or 'ignore'.
               The Caching process looks here for new values to include.

 alerts        data about Alerts

               [id, pvname, name, mailto, mailmsg, compare, trippoint,
                timeout, active, status]

 pairs         data for Related PVsid, 
 
               [pv1, pv2, score]

 instruments   list of instruments
       
               [id, name, station, notes]

               station holds the ID from the stations table.  

 stations      list of stations 

               [id, name,  notes]

 instrument_pvs  data to map PVs with instruments
  
                [id, pvame, inst]

 instrument_positions     data for saved positions for instrument

                [id, name, inst, active, ts]


** Structure of the Archive Database:

The archive databases, with names like pvdata_00001, is is slightly more
complicated than the master database, in an effort to make an efficient
system for archiving thousands of PVs.  There is a main PV table
that holds information about the PVs being archived, including their data
type, archiving deadtime and deadband, and which Data Table to use for data
storage.  There are 128 Data Tables pvdata_00001, pvdata_00002, ...  ....
pvdata_00128.  Because many PVs rarely change, while others change very
frequently, it was found to be inefficient for each PV to have its own data
table, or to have one data table for all archived data.  Instead, when
adding a PV to the archive, the PV name is hashed to give a number
between 1 and 128, and that determines which data table to use.  Of course,
multiple PVs then store to any single table, so a way to identify the PV in
the data table is needed.  When looking up data for a PV, which table is
read from needs to be determined (the table name is stored in the
PV table, so this is very fast) but then only that one table needs
to be read, eliminating more than 99% of the data in the archive.

The PV table has the following columns and meanings:
Column         Description
 id            integer ID
 name          PV name
 description   description of PV
 data_table    name of corresponding data table
 deadtime      deadtime for archiving 
 deadband      deadband
 graph_hi      default high value for plotting range
 graph_lo      default low value for plotting range
 graph_type    default type for plotting: 'normal','log','discrete'
 type          PV data type
 active        Whether PV is actively being archived.

In contrast, the data tables are much simpler, with columns of pv_id (that
is the id from the PV table), time, and value

For further details, simply explore the MySQL databases. 
