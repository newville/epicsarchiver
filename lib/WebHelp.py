#!/usr/bin/env python

from  config import template_dir, cgi_url

conf = {'template_dir':template_dir, 'cgi_url': cgi_url }

conf['adminpage']   = "%s/admin.py"  % cgi_url
conf['plotpage']    = "%s/viewer.py" % cgi_url
conf['instpage']    = "%s/instruments.py" % cgi_url
conf['pvinfopage']  = "%s/admin.py/pvinfo"      % cgi_url
conf['relpv_page']  = "%s/admin.py/related_pvs" % cgi_url
conf['alertpage']   = "%s/admin.py/list_alerts"   % cgi_url
conf['helppage']    = "%s/help.py" % cgi_url
helppage = conf['helppage']




setup = """
<font size=+1>Epics PV Archiver Setup and Management</font></p>


This page gives a few details for setting up and managing the Epics PV
Archiver system.   Installation instructions are in the source kit.


<h4>The command-line pvarch process</h4>

From the linux command line, the main interface to the PV Archiver is the
<tt>pvarch</tt> process.  Typical usages of this command are:

<table align='center'>
<tr><td width=30%%>Command</td><td width=70%%> Meaning</td></tr>
<tr><td colspan=2></td></tr><tr><td colspan=2> <font color='#440099'>Status / General Information</font> </td></tr>

<tr><td><tt>pvarch -h       </tt></td><td>  shows a status message. </td></tr>
<tr><td><tt>pvarch status   </tt></td><td>  shows cache and archiving status, some recent statistics. </td></tr>
<tr><td><tt>pvarch check    </tt></td><td>  print # of archived PVs in past 10 minutes. Should be >1! </td></tr>
<tr><td><tt>pvarch list     </tt></td><td>  prints a list of recent data archives </td></tr>
<tr><td><tt>pvarch save     </tt></td><td>  save a list of recent data archives </td></tr>

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
<tr><td><tt>pvarch drop_pv    </tt></td><td>    remove a PV from cahce and archive </td></tr>

</table>



<h4>Rotating databases, cron jobs</h4>

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

<p> Looking up a PV's value for plotting or data retrieval will seemlessly
span multiple databases, so you don't have to worry about how often you
start a new run.

<p> Because of this, putting <tt>pvarch next</tt> in a cron table to run
once a week or once a month, or at some other frequency, is recommended.  I
would not recommend using a new database more often than once a day, and
once a month seems about right.

<p> Also, because both <tt>pvarch start</tt> and <tt>pvarch cache
start</tt> will do nothing if there is a successfully running archiving and
caching process, you can also put these two commands in cron tables,
running more often to ensure that the caching and archiving are running.


<p> To save the database tables to simple mysql dump files, use <tt>pvarch
save PVDATA_00001</tt>



<h4>Deadtimes: setting how often a PV is recorded</h4>


<h4>Database layout</h4>



"""


overview = """
<font size=+1>Epics PV Archiver Overview</font></p>

The Epics PV Archiver saves Epics PVs into a MySQL database and provides a web
interface for looking up, plotting, and managing the archiving process.  The Archiver
can easily accomodate thousands of PVs and save and retrieve data for many years.<p>

The PV Archiver provides <i>Alerts</i>, which will send an email notification when a
particular PV goes out of an acceptable range.  It also provides a concept of an
<i>Instrument</i>, which is a group of PVs for which you may want to save and look
up positions.

<h4>Caching and Archiving Processes</h4>

The Epics PV Archiver uses two running processes:
<ul>
<li>The <b>Caching Process</b> reads the Epics PVs as fast as it can and stores their
    values into a database cache, where other processes can read the "current value".
    Using this cache cuts down on the number of Epics Channel Access connections need
    to be made, and aslo speeds up access to the data values. The caching process also
    manages the email alerts and instruments.

<li>The <b>Archiving Process</b> reads the set of Epics PVs from the cache and archives
    them into a separate database.  Not every change is archived, as detailed below.

</ul>

Normally, you do not need to think very much about these two processes
except that they both need to be running.  The <a
href="%(adminpage)s">Setting / Admin page </a> will show the current status
of the two processes, including the number of PVs updated in the cache and
the number archived recently. For both of these, there should be a
substantial amount of activity.  See <a
href="%(helppage)s?section=setup">Setup Help</a> for more information on
managing these processes.


<h4>Adding PVs to the Archive</h4>

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

<h4>Adding Motor PVs</h4>

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

<h4>Related PVs</h4>

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


<h4>Web Pages</h4>

Controlling the layout and details of the main Web Status Pages is discussed on the
<a href="%(helppage)s?section=templates">Web Page Template</a> Page.

""" % conf

alerts = """
<font size=+1>Epics PV Archiver Alerts</font></p>

Alerts are used to send an email when a PV goes into an 'Alert' condition.
The alert condition is set by the user, and does not need to be related to
Alarm states for Epics Variables.  To set or change an alert, you will be
challenged for the administrator password.  As with all administrative
tasks for the Archiver, this is a security measure so that only trusted
users can set up emails sent from your system.
To set up Alerts, a mail server and "from address" must be configured at
installation time.
<p>

Use the main <a href="%(alertpage)s">Alert Page</a> for a list of currently
defined alerts.  From this page you can select a "View/Change" link to modify
any of the settings for a particular alert.

<h4>Setting an Alerts</h4>

Alerts are set for a single PV.  In addition to the PV name, each alert
also has a label which can be used to describe the alert, and so that
multiple alerts can be set on a single PV (one person may want an alert
when a valve closes, while another person may want an alert when it
opens!).

<p>
Each alert consists of 3 pieces: a PV's value, a 'test condition' and a
'test trip point'.  When the PV's value meets the test condition, the Alert
is said to be in the 'Alarm' state.     The possible test conditions are:
<ul>
<li> not equal to 
<li> equal to     
<li> less than or equal to 
<li> less than
<li> greater than or equal to
<li> greater than
</ul>

Thus, if a PV's value is 1.8, the condition is 'greater than', and the trip
point is 2.0, the Alert will be in the 'OK' state.  If the PV's value changes
to 2.1, the Alert will be in the 'Alarm' state.

<p> An email notice is sent to the specified addresses when the Alert
changes from 'OK' to 'Alarm'.  Even if the PV's value changes while in the
'Alarm' state or stays in the 'Alarm' state indefinitely, <b> more emails
will NOT be sent</b>.     In addition, each Alert has a 'Time Out' value. Once
an email has been sent for an alert, no email will be sent for that alert for
this time (in seconds).  This is provided to avoid multiple emails for a value
that may rapidly fluctuate about its trip point.


<h4>Customizing and Formatting an Alert email</h4>

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
Thus, you coud customize the message to be:

<pre>

Hello,
   An alarm labeled %%LABEL%%
   was detected because %%PV%% = %%VALUE%%.

   Other PV Values at the time of this alert were:
        Valve 1 : %%PV(Valve1.VAL)%%
        Current : %%PV(Current.VAL)%%

</pre>

To get a more complete report.

The mail message will always have a Subject line that starts with
<tt>[Epics Alert]</tt>, so you can set up auto-forwarding and mail sorting
rules, and will always include a web link to the PV plot page.

<h4>Managing Alerts</h4>

From the web page for Alerts, each can be set to be inactive and then be
re-activated later.  This can be useful to temporarily supress messages for
PVs that are not always critical.    Alerts can also be deleted completely.

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
small buttons will pop-up a calender than can be used to chose the date and
time for these time ranges.

<p> The plot should be shown automatically, and labeled well enough to
interpret the data.  In addition, links are provided for:
<ul>
<li> data file(s) with the real data for each PV

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






"""

templates = """
<font size=+1>Epics PV Archiver Templates and Web Page Layout</font></p>

The web status pages are automatically generated from the template 
files in the 'web template directory', which in this installation
are in the directory: <tt> %(template_dir)s </tt>

<p>
Each template file can list many PVs, typically grouped logically, 
and will be shown as a separate 'Notebook Tab' in the status page, 
with the pages title. The template format for each of these template 
files is detailed below.

<h4>Ordering of Pages / Overall Structure</h4>

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
You do NOT need to run 'make; when you change a template file -- 
these are read on the fly.


<h4>Template Formating:</h4>


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

The descripton shown can be found automatically from the PVs own 
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
detector, or group of motors that make up a sample stage.  For each
of these cases, you may want to know what <i>all the PV values</i> were
at a particular time, and optionally to "restore" the settings to a
previous set of values.
<p>
This is the role of an Instrument in the Epics PV Archiver.

<h4>Instrument naming and hierarchy</h4>

Instruments are categorized with two names, a "Station Name" and an "Instrument Name".
This allows some separation of roles, and provides some hierarchy for finding Instruments.
Each of the two names is a regular string.  Generally, the Station Name will be shorter,
but this is not necessary.

<p>
In addition, each Instrument contains a list of named "Positions".  Instrument Positions are
simply named timestamps which can be used to later get the values of all the PVs in the Instrument
for this position.

<p><b>Important Note:</b>: The PV values are not stored themselves when naming a Position.  Rather the
TimeStamp is used to look up Archived Values.  This has a few consequences:
<ul>
<li> As PVs are added / subtracted to an Instrument, existing Position names do not become
     meaningless, but do retain the meaning of "where were all these PVs at this time?".
<li> If defining an instrument with PVs that are not currently being archived, it may take a 
     minute before the Archive Process actually starts recording that PV.
<li> If PVs are moving very fast, or have long "Archiving Deadtimes", the saved timestamp
     may be slightly out-of-date.
</ul>


<h4>Defining a new Instrument</h4>

The <a href=%(instpage)s>Instruments Page</a> allows to choose from a list
of existing stations or to create a new station.  Once a Station is chosen,
you can choose from a list of existing Instruments or add a new instrument
to this station.

<p> To add a new instrument, you can enter an Instrument Name, description, and enter
a list of PVs.  The definition of an instrument can be modified later, so that PVs can
be added or removed later.  There is no limit on how many PVs can make up an
Instrument.

When you define an instrument, all the PVs in that instrument are given an initial
"Related PV score", so they will all appear as related to one another.

<p> Selecting an Instrument will show a page where you can

<ul>
<li> Save the current position by name.
<li> Lookup a position by date.
<li> view a list of currently named positions.
<li> view and modify the list of PVs that make up this instrument.
</ul>

From this page you can also "Manage Positions" which will be discussed below.

<h4>Named Instrument Positions and Looking up and Restoring Positions</h4>

To save the current position of an instrument, simply type the name of the position
and hit 'Save'.  You can also save an old position, by looking it up by date.

Choosing one of the named positions (or looking up a position by date) will bring up a
page that shows the archived values and the current values for each PV in the
instrument. <p>

In addition, You can generate an IDL script, a Python script, or a Save/Restore file
that you can use to restore the position settings.

<h4>Managing (hiding, deleting) Instrument Positions</h4>

Selecting "Manage Positions" from the Position list will bring up a list of all named
positions for an instrument.  For each of these, you can change the status to one of
'Active', 'Hidden', or 'Delete Forever'.

Here, an 'Active' Position is one currently in use, and that shows up on
the main list of Positions.  A 'Hidden' Position is currently not in use,
and does not show up on the main list of Positions, and so cannot easily be
viewed or restored.  This is useful if you want to temporarily disable some
settings for an Instrument, but may want to return to these settings later.

<p>In addition, you can delete a position forever, which really will erase
it.


""" % conf



from HTMLWriter import HTMLWriter
class WebHelp(HTMLWriter):

    sections = {'overview':overview,
                'plotting':plotting,
                'templates':templates,
                'instruments':instruments,
                'alerts':alerts,
                'setup':setup}

    snames = ('overview', 'plotting', 'templates',
              'instruments', 'alerts',  'setup')

    html_title = 'Epics PV Archiver Help'
    def __init__(self,section=None,anchor=None,**kw):
        HTMLWriter.__init__(self)
        self.section = section or 'main'
        self.anchor  = anchor or ''

    def show(self,section=None,anchor=None,**kw):
        if section is not None: self.section = section
        if anchor is not None: self.anchor = anchor
        
        self.starthtml()
        self.show_links()      
        
        if section not in self.sections.keys(): section = 'overview'
        
        self.write("<h4>Epics PV Archiver Documentation: %s</h4>" % section.title())

        sout = [self.link(link="%s?section=%s" % (helppage,s), text=s.title()) for s in self.snames]
        links = "<p>Help Section: [%s]<p>" % '&nbsp;|&nbsp;'.join(sout)
                   
        self.write("%s<hr>%s %s<hr>" % (links, self.sections[section], links) )

        self.endhtml()
        return self.get_buffer()
