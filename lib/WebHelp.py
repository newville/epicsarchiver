#!/usr/bin/env python
from EpicsArchiver import HTMLWriter, config, __version__

xdbname1 = config.dat_format % (config.dat_prefix,1)
xdbname2 = config.dat_format % (config.dat_prefix,2)
xdbname128 = config.dat_format % (config.dat_prefix,128)

conf = {'template_dir':config.template_dir,
        'cgi_url': config.cgi_url,
        'logdir':  config.logdir,
        'data_dir':config.data_dir,
        'master_db': config.master_db,
        'pvdat1': xdbname1,
        'pvdat2': xdbname2,
        'pvdat128': xdbname128,
        'pv_deadtime_dble': str(config.pv_deadtime_dble),
        'pv_deadtime_enum': str(config.pv_deadtime_enum)  }

conf['adminpage']  = "%s/admin/"  % config.cgi_url
conf['plotpage']   = "%s/plot" % config.cgi_url
conf['instpage']   = "%s/instrument" % config.cgi_url
conf['pvinfopage'] = "%s/admin/pvinfo"        % config.cgi_url
conf['relpv_page'] = "%s/admin/related_pvs"   % config.cgi_url
conf['alertpage']  = "%s/admin/list_alerts"   % config.cgi_url
conf['imgdir']     = "%s/images"              % config.cgi_url
conf['helppage']   = "%s/help"                % config.cgi_url
helppage = conf['helppage']


about = """
The current version of Epics PV Archiver is %s.<p>


The Epics PV Archiver was written by M. Newville at the University of Chicago.  The
latest source code and documentation is available at 
  <a href='http://millenia.cars.aps.anl.gov/~newville/Epics/PVArchiver/'>
  http://millenia.cars.aps.anl.gov/~newville/Epics/PVArchiver/</a>.
""" % __version__

setup = """
<font size=+1>Epics PV Archiver Setup and Management</font></p>

This page gives a few details for setting up and managing the Epics PV
Archiver system.   Installation instructions are in the source kit.

<p>As described in the Overview, the Epics PV Archiver has two main data
stores for PV data, each controlled by a separate running process on the
server:

<ul>
<li>The <b>Caching Process</b> maintains a <i>cache table</i> of current
values for all all Epics PVs.  This manages all Epics connections, and runs
as fast as possible, but stores only the most recent value for any PV.
This cache is used by all other processes, including dynamic web pages and
the archiving process.  The caching process is also responsible for sending
emails for Alerts.  The main point of the cache is to allow different
processes to get current values of Epics PVs without having to make an
actual Channel Access connection.

<li> The <b>Archiving Process</b> stores data for PVs into archives for
later retrieval.  This works by reading recent changes from the cache, and
storing these changes into data tables.  Since many PVs change by a small amount
rather frequently, parameters  can be set to limit the number of changes recorded.
</ul>

Both processes will write log files to %(logdir)s.

<h3>The command-line pvarch process</h3>

The main administrative interface to the PV Archiver is the command line
program <tt>pvarch</tt>.  Typical usages of this program are:

<table align='center'>
<tr><td width=30%%>Command</td><td width=70%%> Meaning</td></tr>
<tr><td colspan=2></td></tr><tr><td colspan=2> <font color='#440099'>Status / General Information</font> </td></tr>

<tr><td><tt>pvarch -h       </tt></td><td>  shows a status message. </td></tr>
<tr><td><tt>pvarch status   </tt></td><td>  shows cache and archiving status, some recent statistics. </td></tr>
<tr><td><tt>pvarch check    </tt></td><td>  print # of archived PVs in past 10 minutes. Should be >1! </td></tr>
<tr><td><tt>pvarch list     </tt></td><td>  prints a list of recent data archives </td></tr>
<tr><td><tt>pvarch save     </tt></td><td>  create backup files of recent data archives </td></tr>
<tr><td><tt>pvarch clean    </tt></td><td>  clean out old files in the web data directory</td></tr>

<tr><td colspan=2></td></tr><tr><td colspan=2> <font color='#440099'>The Archiving Process</font> </td></tr>
<tr><td><tt>pvarch start    </tt></td><td>    start the archiving process </td></tr>
<tr><td><tt>pvarch stop     </tt></td><td>    stop the archiving process </td></tr>
<tr><td><tt>pvarch restart  </tt></td><td>    restart the archiving process </td></tr>
<tr><td><tt>pvarch next     </tt></td><td>    restart with 'next run' of data archives   </td></tr>

<tr><td colspan=2></td></tr><tr><td colspan=2> <font color='#440099'>The Caching Process</font> </td></tr>
<tr><td><tt>pvarch cache start     </tt></td><td>   start cache process (if it's not already running) </td></tr>
<tr><td><tt>pvarch cache stop      </tt></td><td>   stop  cache process </td></tr>
<tr><td><tt>pvarch cache restart   </tt></td><td>   restart cache process </td></tr>
<tr><td><tt>pvarch cache status    </tt></td><td>   show # of PVs cached in past 60 seconds  </td></tr>
<tr><td><tt>pvarch cache activity  </tt></td><td>   show list of PVs cached in past 60 seconds </td></tr>

<tr><td colspan=2></td></tr><tr><td colspan=2> <font color='#440099'>Adding and removing PVs</font> </td></tr>
<tr><td><tt>pvarch add_pv     </tt></td><td>    add a PV to the cache and archive </td></tr>
<tr><td><tt>pvarch add_pvfile </tt></td><td>    read a file of PVs to add to the Archiver </td></tr>
<tr><td><tt>pvarch drop_pv    </tt></td><td>    remove a PV from cache and archive </td></tr>

</table>


<h3>Deadtime and Deadbands: setting how often a PV is recorded</h3>

While the caching process saves current values for all PVs as fast as it
can, it is not necessary to store <i>all</i> changes to PVs.  Two
parameters set how often values are archived: the <i>deadtime</i>, and the
<i>deadband</i>.  Both of these can be set for each PV.

<p>
The <i>deadtime</i> for a PV sets how long to wait after archiving a PVs
value before archiving another value for this PV.  Let's take as an example
a deadtime of 10 seconds.  If the PV hasn't changed in longer than 10
seconds, then a change to the value will be archived as quickly as
possible.  But if the value changes again within 10 seconds, the change
will not be recorded immediately.  Instead, the change will be seen and the
archiver will wait until 10 seconds has elapsed since the last time the
value was recorded.  This way, if multiple changes happen during that 10
seconds, the only value recorded will be the one held after 10 seconds has
elapsed -- all intermediate changes will be forgotten.

<p> One thing to note, though, is that the time of the last change will be
recorded properly.  Thus, if a value changes, changes again 1 second later,
and then stays fixed, the archiver will record the changes as taking place
1 second apart.

<p>

The <i>deadband</i> for a PV sets how big a fractional change must be in
order to be archived.

<p>

When PVs are added to the database, typical deadtimes are one or a few
seconds, depending on whether the PV has a type 'double' -- which can
easily change trivial amounts -- or a type of 'int','enum', or 'string',
which change less often.  For this setup, the default deadtime for PVs of
type 'double' or 'float' is %(pv_deadtime_dble)s seconds, while the default
deadtime for all other PVs is %(pv_deadtime_enum)s seconds.  Typical
deadbands are set small enough to be not actually effective.


<h3>Rotating databases, cron jobs</h3>

The archiving process writes data to a single database (more details on
database layout is below).  It is expected and encouraged to have several
of these archive databases, each one representing a 'run' for a fixed time
duration, typically around a weeks to a month.  

<p> That is, you will want to periodically start archiving into a new
database.  Using <tt>pvarch next</tt> will tell the Archiver to make the
"next" database in the series of archives and to start collecting into that
new database.  All PVs archived and all their settings in the old database
will be moved into the new one. Using <tt>pvarch list</tt> will show a list
of the most recent 'runs'.

<p> Looking up a PV's value for plotting or data retrieval will seamlessly
span multiple databases, so you don't have to worry about how often you
start a new run.  Because of this, putting <tt>pvarch next</tt> in a cron
table to run once a week or once a month, or at some other frequency, is
recommended.  I would not recommend using a new database more often than
once a day -- once a month or every few weeks seems about right.

<p> Also, because both <tt>pvarch start</tt> and <tt>pvarch cache
start</tt> will do nothing if there is a successfully running archiving and
caching process, you can also put these two commands in cron tables,
running more often to ensure that the caching and archiving are running.

<p>Another potential use of a cron job can be to clean out the data files
created for the data plotting and viewing.  These are temporary files
stored in %(data_dir)s.  To clean old files in this directory, you can use
the command

<pre>

pvarch clean

</pre>

<p> Finally, to backup the databases with simple mysql dump files, use
<tt>pvarch save</tt>.  This will save the two principle databases: the
master database, %(master_db)s, and the currently active archive database.
You can specify additional databases to save as command-line arguments:

<pre>

pvarch save %(pvdat1)s

</pre>

Example crontab files for these tasks are included in the source distribution.

<h3>Database layout</h3>

This Epics PV Archiver has two main databases that it uses.  The main or
master database, named %(master_db)s, holds the cache of values, status
information about running processes, the history of archive 'runs',
settings for Instruments and Alerts, and the data for related PVs.  The
archive database holds the archived values for the PVs as well as data
about how to archive the data.

<p>
At any one time, one archive database is 'current', meaning that it is the
one be written to, so the database in use is a sequentially number
database, of the form %(pvdat1)s, %(pvdat2)s, ....  Each databases holds a
set of data for a specific time period -- a 'run'. Data retrieval uses the
full set of archive databases, and looks up older spanning archive
databases as necessary.

<p> The assumption is that the Python programming interface will be used to
access data in the PV Archive.  While the data is stored with MySQL
databases, using simple SQL queries to retrieve data from the PV Archive is
slightly non-trivial.  Still, for completeness, a partial description of
the databases is provided here:

<h4>Structure of the Master Database:</h4>

The master database, %(master_db)s, is a fairly simply database.  There are
several tables, but none of them is very complicated, and the logic that
joins them is fairly simple.  The tables are:

<table><tr><td>Table</td><td>Description</td><td>Data Columns</td></tr>
<tr> <td>cache</td><td> holds the cached data for all PVs.</td>
<td> <tt>id, pvname,type, value, cvalue, ts, active</tt></td></tr>
<tr><td></td><td></td><td>
                  <tt>cvalue</tt> is the 'character string value',
                  <tt>ts</tt> is the timestamp, <tt>active</tt> holds whether
                  the PV is actively cached.</td><tr>

<tr> <td>runs</td><td> holds info about archiving 'runs'.</td><td> <tt>id, db,notes, start_time,stop_time</tt>
<tr><td></td><td></td><td> <tt>db </tt> is the name of the current archive databases.</td></tr>
                  
<tr> <td>info</td><td> status information about running 'cache' and 'archive' processes</td>
<td> <tt>id, process, status, db, datetime, ts, pid</tt></td></tr>
<tr><td></td><td></td><td> <tt>process</tt> is either 'cache' or 'archive'.</td></tr>

<tr> <td>requests</td><td>temporary storage for requested changes to the cache database</td>
<td><tt>id, pvname, action</tt></td></tr>
<tr><td></td><td></td><td> <tt>action</tt> is 'add', 'drop', 'suspend', or 'ignore'.
                             The Caching process looks here for new values to include.</td></tr>

<tr> <td>alerts</td><td>data about Alerts
<td><tt>id, pvname, name, mailto, mailmsg,
                  compare, trippoint, timeout, active, status</tt></td></tr>

<tr> <td>pairs</td><td>data for Related PVs</td><td><tt>id, pv1, pv2, score</tt></td></tr>

<tr> <td>instruments</td><td>list of instruments<td><tt>id, name, station, notes</tt></td></tr>
<tr><td></td><td></td><td><tt>station</tt> holds the ID from the stations table. </td></tr>

<tr> <td>stations</td><td>list of stations</td><td> <tt>id, name,  notes</tt> </td></tr>

<tr> <td>instrument_pvs</td><td>data to map PVs with instruments</td>
<td><tt>id, pvame, inst</tt></td></tr>

<tr> <td>instrument_positions</td><td>data for saved positions for instrument</td>
<td><tt>id, name, inst, active, ts</tt></td></tr>

</table>

<h4>Structure of the Archive Database:</h4>

The archive databases, with names like %(pvdat1)s, is is slightly more
complicated than the master database, in an effort to make an efficient
system for archiving thousands of PVs.  There is a main <tt>PV</tt> table
that holds information about the PVs being archived, including their data
type, archiving deadtime and deadband, and which Data Table to use for data
storage.  There are 128 Data Tables %(pvdat1)s, %(pvdat2)s, ...  ....
%(pvdat128)s.  Because many PVs rarely change, while others change very
frequently, it was found to be inefficient for each PV to have its own data
table, or to have one data table for all archived data.  Instead, when
adding a PV to the archive, the PV name is <i>hashed</i> to give a number
between 1 and 128, and that determines which data table to use.  Of course,
multiple PVs then store to any single table, so a way to identify the PV in
the data table is needed.  When looking up data for a PV, which table is
read from needs to be determined (the table name is stored in the
<tt>PV</tt> table, so this is very fast) but then only that one table needs
to be read, eliminating more than 99%% of the data in the archive.

<p>The <tt>PV</tt> table has the following columns and meanings:
<table><tr><td>Column</td><td> Description</td></tr>
<tr><td> id</td><td>          integer ID</td></tr>
<tr><td> name</td><td>        PV name</td></tr>
<tr><td> description </td><td>  description of PV</td></tr>
<tr><td> data_table</td><td>  name of corresponding data table</td></tr>
<tr><td> deadtime</td><td>    deadtime for archiving </td></tr>
<tr><td> deadband</td><td>    deadband</td></tr>
<tr><td> graph_hi</td><td>    default high value for plotting range</td></tr>
<tr><td> graph_lo</td><td>    default low value for plotting range</td></tr>
<tr><td> graph_type</td><td>  default type for plotting: 'normal','log','discrete'</td></tr>
<tr><td> type</td><td>   PV data type</td></tr>
<tr><td> active</td><td> Whether PV is actively being archived.</td></tr>
</table>

<p>In contrast, the data tables are much simpler, with columns of
<tt>pv_id</tt> (that is the <tt>id</tt> from the PV table), <tt>time</tt>, and
<tt>value</tt>

<p>For further details, simply explore the MySQL databases. 

""" % conf

overview = """
<font size=+1>Epics PV Archiver Overview</font></p>

The Epics PV Archiver saves Epics PVs into a MySQL database and provides a web
interface for looking up, plotting, and managing the archiving process.  The Archiver
can easily accommodate thousands of PVs and save and retrieve data for many years.<p>

The PV Archiver provides <i>Alerts</i>, which will send an email notification when a
particular PV goes out of an acceptable range.  It also provides a concept of an
<i>Instrument</i>, which is a group of PVs for which you may want to save and look
up positions.

<h3>Caching and Archiving Processes</h3>

The Epics PV Archiver uses two running processes:
<ul>
<li>The <b>Caching Process</b> reads the Epics PVs as fast as it can and stores their
    values into a cache database, where other processes can read the "current value".
    Using this cache cuts down on the number of Epics Channel Access connections need
    to be made, and speeds up access to the data values. The caching process also
    manages the email alerts and instruments.

<li>The <b>Archiving Process</b> reads the set of Epics PVs from the cache
    and archives them into a separate database.  Not every change is
    archived, as detailed in the Setup section.

</ul>

Normally, you do not need to think very much about these two processes
except that they both need to be running.  The <a
href="%(adminpage)s">Setting / Admin page </a> will show the current status
of the two processes, including the number of PVs updated in the cache and
the number archived recently. For both of these, there should be a
substantial amount of activity.  See <a
href="%(helppage)s?section=setup">Setup Help</a> for more information on
managing these processes.

<h3>Adding PVs to the Archive</h3>

There are a few ways to add PVs to the archive, all of them very easy.
<p>

First, you can use the command line program <tt>pvarch</tt>, with
<pre>

   ~> pvarch add_pv MyPV.VAL
</pre>
You can add multiple PVs on a single line:


<pre>

   ~> pvarch add_pv MyPV1.VAL  MyPV2.VAL
</pre>

This will add both PVs, and also set them as "related PVs", which will show
up in the plot view page.

Second, you can put a list of PVs in a file, either one per line or
multiple PV names per line (separated by a space or comma), and run

<pre>

   ~> pvarch add_pvfile PVList.txt
</pre>

This is probably most useful on initial setup or when adding a large set of
new PVs.  As with <tt>pvarch add_pv</tt>, putting multiple PVs on a single
line will make the "Related".

<p>
The third way to add PVs is to put them in one of the template files for
the web status pages (See the <a href="%(helppage)s?section=templates">Template</a> Page
for details).  The next time the corresponding web page is accessed, the
system will see that the PV is not included, will initially report 'Unknown',
and request it to be added to the Cache and Archive processes.

<p>
For all these methods, the PV will not actually be added unless it is a
valid Epics PV that can be accessed from the server.  In some cases, you
may wish to record remote PVs -- you'll want to set EPICS_ADDR_LIST
accordingly.

<h3>Adding Motor PVs</h3>

When adding a PV for a Motor (that is, one that has a record type of
'motor' from the Epics Motor Record), all of the following fields will
automatically be added, and all pairs of PVs will be set to be related:

<ul>
<li> <tt>.VAL</tt>   Value
<li> <tt>.DESC</tt>   Description
<li> <tt>.OFF</tt>   Offset
<li> <tt>.FOFF</tt>  Freeze Offset
<li> <tt>.DIR</tt>   Direction
<li> <tt>.SET</tt>   Set Value
<li> <tt>.HLS</tt>   High Limit is Set
<li> <tt>.LLS</tt>   Low Limit is Set
<li> <tt>_able.VAL</tt>   Motion is Enabled
<li> <tt>.SPMG</tt>      Stop/Pause/Move/Go
</ul>

This subset of all the fields of the motor record are thought to be enough
to reconstruct "where a motor was" and/or "what happened to the alignment
questions".

<h3>Related PVs</h3>

As alluded to above, there is a concept that some PVs can be "related" to
others.  The Archiver uses a simple scoring method for pairs of PVs, and
pairs of PVs that have a non-zero score are said to be related.  In
addition, any time a pair of PVs are plotted together, the score is
increased, so that they will 'move up' in the list of related PVs.

<p> When PV are added to the archive, pairs of PVs will get an initial pair score
of 10 under the following conditions:
<ul>
<li> They are listed on the same command line with <tt>pvarch add_pv</tt>
<li> They are listed on the same line of a PV file added with <tt>pvarch add_pvfile</tt>
<li> They are listed on the same line of a web template file.
<li> They are from an Epics Motor.
<li> They are included together in an Instrument.
</ul>

The list of related PVs for any PV can also be managed through the Settings
/ Admin page, where you can adjust the score for any pair of PVs.


<h3>Web Pages</h3>

Controlling the layout and details of the main Web Status Pages is discussed on the
<a href="%(helppage)s?section=templates">Web Page Template</a> Page.

""" % conf

alerts = """
<font size=+1>Epics PV Archiver Alerts</font></p>

Alerts are used to send an email when a PV goes into an 'Alert' condition.
The alert condition in the Epics Archiver is set by the user, and does not
need to be related to Alarm states for Epics Process Variables.  Alerts are
set for a single PV -- currently they cannot depend on complex conditions
of PVs (say, PV1 is greater than 5 AND PV2 is not 0), though an Epics calc
record might be able to provide such logic.<p>


To set or change an alert, you will be challenged for the administrator
password.  As with all administrative tasks for the Archiver, this is a
security measure so that only trusted users can set up emails sent from
your system.  To set up Alerts, a mail server and "from address" must be
configured at installation time.  <p>

Use the main <a href="%(alertpage)s">Alert Page</a> to see a list of currently
defined alerts.  From this page you can select a "View/Change" link to modify
any of the settings for a particular alert.

<p>
Thes main alert page will look like:<br>

<a href='%(imgdir)s/alert1.png'><img src='%(imgdir)s/alert1.png' width=500></a>

<p>

Selecting one the existing alerts, or adding a new  alert will bring up a form like this:<br>

<a href='%(imgdir)s/alert2.png'><img src='%(imgdir)s/alert2.png' width=500></a>

<h3>Setting an Alerts</h3>

<p> In addition to the PV name, each Alert has a label to describe the
alert, and so that multiple alerts can be set on a single PV (one person
may want an alert when a valve closes, while another person may want an
alert when it opens!).  The label will be used in the email sent when the
Alert condition is met.

<p> Each alert consists of 3 pieces: a PV's value, a 'test condition' and a
'trip point'.  When the PV's value meets the condition for that trip point,
the Alert is said to be in the 'Alarm' state.  The possible test conditions
are:

<ul>
   <li> not equal to 
   <li> equal to     
   <li> less than or equal to 
   <li> less than
   <li> greater than or equal to
   <li> greater than
</ul>

As an example, if a PV's value is 1.8, the test condition is 'greater
than', and the trip point is 2.0, the Alert will be in the 'OK' state.  If
the PV's value changes to 2.1, the Alert will be in the 'Alarm' state.

<p> An email notice is sent to the specified addresses when the Alert
changes from 'OK' to 'Alarm'.  If the PV's value changes again, but still
stay in the 'Alarm' state or if it stays in the 'Alarm' state indefinitely,
<b> NO more emails will be sent</b>.  In order for another message to be
sent, the Alert would have to change back to an 'OK' condition', and then
again to an 'Alarm' condition.  In addition, each Alert has a 'Time Out'
value (in seconds). Once an email has been sent for an alert, no email will
be sent for that alert for this time, even if the Alert goes from 'OK' to
'Alarm'.  This is provided to avoid multiple emails for a value that may
rapidly fluctuate about its trip point.


<h3>Customizing and Formatting an Alert email</h3>

By default, the content of the sent email will look something like this:

<pre>

Hello,
   An alarm labeled 'XXX went non-zero'
   was detected for PV = 'XXX.VAL'
   The current value = 1.0. This is
   not equal to the trip point value of 0.0
</pre>


You can customize this message on the Alerts page, putting in any text you
want.  Since you may want to include some of the the name and value of the
PV, and the alert label, condition, and trip point, you can use the
following simple template format for the mail message to automatically get
these values:

<ul>
  <li> <tt>%%PV%%  </tt>:  PV Name
  <li> <tt>%%VALUE%%</tt>:  Current PV Value
  <li> <tt>%%LABEL%%</tt>:  Alert Label
  <li> <tt>%%COMP%%</tt>:  Alert Condition
  <li> <tt>%%TRIP%%</tt>:  Alert Trip Point
  <li> <tt>%%PV(XXX.VAL)%%</tt>:  Value of another PV
</ul>

With the last item, you can get the value for other PVs in the mail message.
For this to work, the other PV must already be added to the Cache and Archive.

<p>
Thus, you could customize the message to be:

<pre>

Hello,
   An alarm labeled %%LABEL%%
   was detected because %%PV%% = %%VALUE%%.

   Other PV Values at the time of this alert were:
        Valve 1 : %%PV(Valve1.VAL)%%
        Current : %%PV(Current.VAL)%%

</pre>

To get a more complete report.  The mail message will always have a Subject
line that starts with <tt>[Epics Alert]</tt>, so you can set up
auto-forwarding and mail sorting rules, and will always include a web link
to the Plot page for the PV.

<h3>Managing Alerts</h3>

From the web page for Alerts, each can be set to be inactive and then be
re-activated later.  This can be useful to temporarily suppress messages
for PVs that are not always critical.  Alerts can also be deleted
completely.

""" % conf

plotting = """
<font size=+1>Epics PV Archiver Plotting and Viewing</font></p>

Plotting and Viewing of PV Data is fairly straightforward using the <a
href="%(plotpage)s?">Archive Viewing Page</a>.  From this page, you can
choose one or two PVs to plot, and the time range for the data to be
plotted.  You can also explicitly set the range for the y-axis (ordinate),
and whether to use normal or log scale for the y-axis.

<p> There are two methods for setting the time range (abscissa).  First,
you can select the 'Time From Present' button and the time length from the
drop down menu (ranging from 15 minutes to 1 month).  Second, you can give
an explicit time range and select the 'Data Range' button.  Here, the
format needs to be "YYYY-mm-dd HH:MM:SS" for both dates.  Clicking on the
small buttons will pop-up a calendar than can be used to chose the date and
time for these time ranges.

<p> The plot should be shown automatically, and labeled well enough to
interpret the data.  In addition, links are provided for:
<ul>

<li> data file(s) with the real data for each PV.


<li> the gnuplot script used to create the plot, in case you'd like to
modify the plot for other purposes.

</ul>

The data format for these data files is a three column ASCII file with
headers marked by lines starting with <tt>#</tt>.  The header will include
some information about time range, and for ENUM PVs, the legend for mapping
integer ENUM values to strings.    The data rows (one per time) will be of the form

<pre>

YYYYMMDD HHMMSS UNIXTS   Value

</pre>

That is, a 4 digit year, a 2 digit month, a 2 digit day, 1 space, a 2 digit
hour, a 2 digit minute, a 2 digit minute, 1 space, a floating point Unix
timestamp (seconds since epoch), 1 space, and the data value.

<p> On the server, the data files, gnuplot scripts, and resulting PNG files
will be stored as temporary file in %(data_dir)s.  These files will be
cleaned out periodically.


""" % conf

templates = """
<font size=+1>Epics PV Archiver Templates and Web Page Layout</font></p>

The web status pages are automatically generated from the template files in
the 'web template directory'.  For this installation, the directory is <tt>
%(template_dir)s </tt>.  There, you will find a <tt>README</tt> file (which
mostly repeats the instructions here), a unix <tt>makefile</tt>, a file
named <tt>pages.py</tt>, a file named <tt>FileList</tt>, and possible
several other files, each containing the template for an individual
'Notebook Tab' web page.
 
<p> Each template file can list many PVs, typically grouped logically, and
will be shown as a separate tab in the status page, with the pages
title. The template format for each of these template files is detailed
below.

<h3>Ordering of Pages / Overall Structure</h3>

The master file <tt>FileList</tt> in the template directory contains the 
list of Title, Template File pairs: 
<p><pre>

Storage Ring | storage_ring.txt
Vacuum System | vacuum.txt

</pre>
<p>

and so on, with Title and File name separated by '|'.  This will 
be used to make the 'Notebook Tabs' in the status page.  For this 
example, there will be two tabs; 'Storage Ring' and 'Vacuum System'.

<p>
To add or change the Tab titles or template files, alter FileList 
and run 'make'.  This will generate pages.py which will be loaded 
by the web scripts.

<p>
You do NOT need to run 'make' when you change a template file:
these are read on the fly.  You do need to run 'make' when you want to
add a new tabbed page, change the titles for each tab, or change the
order in which they appear.

<h3>Template Formatting:</h3>

The status pages contain an HTML table, with each row corresponding to one
or more Epics PVs.  The general idea is to list the PV(s) to be shown.
A simple example would be:

<pre>

 S:SRCurrentAI.VAL

</pre>

This will generally get mapped to a table row that has
<pre>

   Description               Current_Value_with_Link_to_Archive

</pre>

The description shown can be found automatically from the PVs own 
description field, if available.  If it is not available, the PV
name will be used.  In either case, it can be set explicitly set 
by separating with a '|':
<pre>

 S:SRCurrentAI.VAL | Ring Current

</pre>
In addition, the formatting can be explicitly set as well:
<pre>

 S:SRCurrentAI.VAL | Ring Current | %%.2f

</pre>
<p>

For ENUM PVs, the ENUM string will be shown as the Current_Value, 
but it's not uncommon for integer PVs to hold a 'status' field with 
values '0' and '1' (for example, the 'Stations Searched' PVs at the 
APS!)  For these, there a special 'yes/no' format can be used to
map 0 to No, 1 to Yes, and any other value to Unknown.

<p>
To specify the formatting but use the default description, use
<pre>  

 S:SRCurrentAI.VAL | | %%.2f

</pre>
<p>

You can put multiple PVs on a single line, separated by commas:
<pre>  

XXX:m1.VAL, XXX:m2.VAL

</pre>
<p>

Which will list many PVs on a single line.  You'll probably want to 
set the description explicitly:
<pre>  

XXX:m1.VAL, XXX:m2.VAL | Sample Motors (chi, theta)

</pre>

<p>
Other formatting options: a section heading line in red can be
given with <tt>[Title]</tt>, a horizontal rule with <tt>----</tt>,
and an empty row with <tt><></tt>
 
Several examples are provided in the files 'GSE_pageN.txt'

And, again, the template files can be edited 'on-the-fly'.
<hr>

""" % conf


instruments = """
<font size=+1>Epics PV Archiver Instruments</font></p>

Instruments are collections of PVs that can be thought of as a single
group.  Examples of instruments are the settings for an amplifier, a
detector, or group of motors that make up a sample stage.  For each of
these cases, you may want to know <i>all the PV values</i> for a particular
time, and you may want to "restore" the values to those of an earlier time.
This is what an Instrument provides: a way to logically group PVs, and
save, lookup, and restore the values for <i>all</i> PVs in that group.


<h3>Instrument naming and hierarchy</h3>

Instruments are categorized with two names, a "Station Name" and an
"Instrument Name".  This allows some separation of roles, and provides some
hierarchy for finding Instruments.  Each of the two names is simply a string.
Typically, the Station Name will be short name to identify a group of instruments.

<p> Each Instrument is made up of a list of PVs.  There is no limit to the
number of PVs in an Instrument, nor is there a limit on how many different
intruments a single PV can be part of.  This list of PVs for an instrument
can be altered over time.

<p> Each Instrument has a list of named "Positions".  Instrument Positions are
very simple: they are names for the <b>time</b> at which the Position is
defined.  This time can then be used to later retrieve the values of all
the PVs in the Instrument for this position.

<p><i>Important Note:</i> The PV values themselves are <i>not</i> stored
naming a Position.  Only the <i>time</i> is stored. This has a few
consequences:

<ul>
<li> As the PVs that make up an Instrument might chage, existing Position
     names do not become meaningless, but retain the meaning of "where
     were all the PVs currently defined for this Instrument at this time?".
     Of course, if an Instrument now contains a PV that was not being archived
     until  recently, that PV's value may not be known.
<li> If defining an instrument with PVs that are not currently being
     archived, it may take a minute before the Archive Process actually
     starts recording that PV.
<li> If PVs are moving very fast, or have long "Archiving Deadtimes", the
     saved timestamp may be slightly out-of-date.
</ul>


<h3>Defining a new Instrument</h3>

The <a href=%(instpage)s>Instruments Page</a> allows to choose from a list
of existing stations or to create a new station.  Once a Station is chosen,
you can choose from a list of existing Instruments or add a new instrument
to this station.

<p> To add a new instrument, you can enter an Instrument Name, description,
and enter a list of PVs.  The definition of an instrument can be modified
later, so that PVs can be added or removed later.  There is no limit on how
many PVs can make up an Instrument.

When you define an instrument, all the PVs in that instrument are given an
initial "Related PV score", so they will all appear as related to one
another.

<p> Selecting an Instrument will show a page where you can

<ul>
   <li> Save the current position by name.
   <li> Lookup a position by date.
   <li> view a list of currently named positions.
   <li> view and modify the list of PVs that make up this instrument.
</ul>

From this page you can also "Manage Positions" which will be discussed below.

<h3>Named Instrument Positions and Looking up and Restoring Positions</h3>

To save the current position of an instrument, simply type the name of the
position and hit 'Save'.  You can also save an old position, by looking it
up by date.

Choosing one of the named positions (or looking up a position by date) will
bring up a page that shows the archived values and the current values for
each PV in the instrument. <p>

In addition, You can generate an IDL script, a Python script, or a
Save/Restore file that you can use to restore the position settings.

<h3>Managing (hiding, deleting) Instrument Positions</h3>

Selecting "Manage Positions" from the Position list will bring up a list of
all named positions for an instrument.  For each of these, you can change
the status to one of 'Active', 'Hidden', or 'Delete Forever'.

Here, an 'Active' Position is one currently in use, and that shows up on
the main list of Positions.  A 'Hidden' Position is currently not in use,
and does not show up on the main list of Positions, and so cannot easily be
viewed or restored.  This is useful if you want to temporarily disable some
settings for an Instrument, but may want to return to these settings later.

<p>In addition, you can delete a position forever, which really will erase
it.


""" % conf



section_map = {'overview':overview,
               'plotting':plotting,
               'templates':templates,
               'instruments':instruments,
               'alerts':alerts,
               'setup':setup,
               'about':about}
section_names  = ('overview', 'plotting', 'templates',
                  'instruments', 'alerts',  'setup','about')



class WebHelp(HTMLWriter):


    html_title = 'Epics PV Archiver Help'
    def __init__(self,section=None,anchor=None,**kw):
        HTMLWriter.__init__(self)
        self.section = section or 'main'
        self.anchor  = anchor or ''

    def show(self,section=None,anchor=None,**kw):
        if section is not None: self.section = section
        if anchor is not None: self.anchor = anchor
        
        self.starthtml()
        self.show_links(active_tab='Help')
        
        if section not in section_map.keys(): section = 'overview'
        
        self.write("<h3>Epics PV Archiver Documentation: %s</h3>" % section.title())

        sout = [self.link(link="%s/%s" % (helppage,s), text=s.title()) for s in section_names]
        links = "<p>Help Section: [%s]<p>" % '&nbsp;|&nbsp;'.join(sout)
                   
        self.write("%s<hr>%s %s<hr>" % (links, section_map[section], links) )

        self.endhtml()
        return self.get_buffer()

def dehtml(s):
    replacements = {'<hr>':'---'*20, '<h3>':'== ','</h3>':' ==',
                    '<h4>':' ** ','</h4>':'',
                    '</a>':'>>','<a href="':'<<'}

    remove_tags = ('hr','b','p','i','h3','h4','pre','a',
                   'li','ul','tt','td','tr','table','font',
                   "font color='#440099'",'td colspan=2',
                   "table align='center'","font size=+1",
                   "td width=30%", "td width=70%")
    
    for k,v in replacements.items(): s = s.replace(k,v)

    for i in remove_tags:
        s = s.replace('<%s>'%i,'').replace('</%s>'%i,'').replace('\n\n\n','\n\n').replace('\t','   ')
    return s

if __name__ == '__main__':
    for name in section_names:        
        print "##== %s ==##" % name.title()
        print dehtml(section_map[name])
        print "========================================="
        
