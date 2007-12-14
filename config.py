#
# configuration file for PV_Archive.py

DEBUG = True

######################################################
##
## Mysql setup section
##
# give the mysql user name, password, and host.
# this account does not need to have access to all tables!!
dbuser = 'epics'
dbpass = 'epics321'
dbhost = 'localhost'

# command for how mysql databases should be 'dumped'.
mysqldump = '/usr/bin/mysqldump --opt -p%s -u%s' % (dbpass,dbuser)

# location of log directories
logdir = '/var/log/pvarch'
if DEBUG:
    logdir='/home/newville/logs/pvarch/'

# name of 'master' database
master_db = 'pvarch_master'

# prefix used for sequentially named databases
# this *MUST* contain lowercase letters only
dat_prefix = 'pvdata'

# format string used for sequentially named databases
# please don't change this without care: the '_' is
# used to split the string, and a 5 digit number will
# allow enough unique databases.
dat_format = "%s_%.5i"

# default PV 'deadtimes': how long after archiving a value
# to wait to record another value.  Changes during the
# deadtime will be seen, but will not be recorded until the
# deadtime has elapsed.  If multiple changes happen during
# the deadtime, only the most recent value will be recorded
# when the deadtime has elapsed.
#    pv_deadtime_enum will be used for ENUM and STRING PVs
#    pv_deadtime_dble will be used for all other PVs
# The deadtime can be adjusted per PV while archiving.

pv_deadtime_dble = 5
pv_deadtime_enum = 1

######################################################
##
## Web setup section
##
#  apache root directory, and the URL 
apache_root = '/var/www/'
url_root    = 'http://idea.cars.aps.anl.gov/'
# apache user / group -- these should be the same as in httpd.conf
apache_user = 'apache'
apache_group= 'apache'

if DEBUG:
    apache_root = '/www/apache/'
    url_root    = 'http://ion.cars.aps.anl.gov/'
    apache_user = 'nobody'
    apache_group= 'nobody'
    

# location for python web scripts, and how this maps to a URL:
cgi_bin   = apache_root  + 'cgi-bin/pvarch'
cgi_url   = url_root     + 'cgi-bin/pvarch'

# location for output data files from PlotViewer and how this maps to a URL:
cgi_data_dir = apache_root + 'html/cgi-data/'
cgi_data_url = url_root    + 'cgi-data/'
data_dir     = cgi_data_dir+ 'pvarch'
data_url     = cgi_data_url+ 'pvarch'

webfile_prefix = 'pv'

# location for javascript calendar used by PlotViewer how this maps to a URL:
#  (this will be installed by setup.py)
jscal_dir     = cgi_data_dir+ 'jscal'
jscal_url     = cgi_data_url+ 'jscal'

# title for status web pages
pagetitle = 'PV Archiver Status Page'

# footer for status web pages
footer = """<hr>[
<a href=http://www.aps.anl.gov/asd/blops/status/smallHistory.html>APS Storage Ring Status</a> |
<a href=http://www.aps.anl.gov/Facility/>APS Facility Page</a>|
<a href=http://www.aps.anl.gov/Accelerator_Systems_Division/Operations_Analysis/logging/MonitorDataReview.html>APS OAG Data</a>
]"""

# location of editable web status template files
#   the files in this directory should be readily editable
#   to customize the PVs displayed in the status page
#   directory needs to be world-readable, but can be in a user directory
share_dir  = '/usr/local/share/pvarch/'

template_dir  = share_dir + 'templates/'

######################################################
##
## Email setup for email alerts
##
mailserver = 'localhost'
mailfrom   = 'pvarchiver@cars.uchicago.edu'


css_style = """
<style type='text/css'>
pre {text-indent: 20px}
h5 {font:bold 14px verdana,arial,sans-serif;color:#042264;}
h4 {font:bold 18px verdana,arial,sans-serif;color:#042264;}
h3 {font:bold 18px verdana,arial,sans-serif;color:#A42424;font-weight:bold;font-style:italic;}
h2 {font:bold 22px verdana,arial,sans-serif;color:#044484;font-weight:bold;}

.h5font {font:bold 14px verdana,arial,sans-serif;color:#042264;}
.h4font {font:bold 18px verdana,arial,sans-serif;color:#042264;}
.h3font {font:bold 18px verdana,arial,sans-serif;color:#A42424;font-weight:bold;font-style:italic;}

.xtitle {font-family: verdana, arial, san-serif; font-size: 13pt;
         font-weight:bold; font-style:italic;color:#900000}
.xx {font-size: 3pt;}
body {margin:10px; padding:0px;background:#FDFDFD; font:bold 14px verdana, arial, sans-serif;}
#content {text-align:justify;  background:#FDFDFD; padding: 0px;border:4px solid #88000;
          border-top: none;  z-index: 2; }
#tabmenu {font: bold 11px verdana, arial, sans-serif;
          border-bottom: 2px solid #880000; margin: 1px; padding: 0px 0px 4px 0px; padding-left: 20px;}
#tabmenu li {display: inline;overflow: hidden;margin: 1px;list-style-type: none; }
#tabmenu a, a.active {color: #4444AA;background: #EEDD88;border: 2px solid #880000;
             padding: 3px 3px 4px 3px;margin: 0px ;text-decoration: none; }
#tabmenu a.active {color: #CC0000;background: #FCFCEA;border-bottom: 2px solid #FCFCEA;}
#tabmenu a:hover {color: #CC0000; background: #F9F9E0;}

#time {font: bold 12px verdana, arial, sans-serif; border: 2px; color: #4444AA; margin: 1px;}
</style>
"""
