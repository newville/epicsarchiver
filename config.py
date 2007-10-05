#
# configuration file for PV_Archive.py
#

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
# logdir = '/var/log/pvarch'
logdir = '/home/newville/logs/pvarch'

# name of 'master' database
master_db = 'pvarch_master'

# name of caching db
cache_db  = 'pvarch_cache'

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
apache_root = '/usr/local/apache/'

apache_root = '/www/apache/'
url_root    = 'http://ion.cars.aps.anl.gov/'

# location for python web scripts, and how this maps to a URL:
cgi_bin   = apache_root  + 'cgi-bin/pvarch'
cgi_url   = url_root     + 'cgi-bin/pvarch'

# location for output data files from PlotViewer and how this maps to a URL:
data_dir  = apache_root + 'htdocs/cgi-data/pvarch'
data_url  = url_root    + 'cgi-data/pvarch'

# location for javascript calendar used by PlotViewer how this maps to a URL:
#  (this will be installed by setup.py)
jscal_dir  = apache_root + 'htdocs/cgi-data/jscal'
jscal_url  = url_root    + 'cgi-data/jscal'

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

template_dir  = '/usr/local/share/pvarch/templates/'
