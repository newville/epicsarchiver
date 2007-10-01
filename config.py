#
# configuration file for PV_Archive.py

######################################################
## Mysql setup section
##
# give the mysql user name, password, and host
dbuser = 'epics'
dbpass = 'epics321'
dbhost = 'localhost'

# command for how mysql databases should be 'dumped'.
mysqldump = '/usr/bin/mysqldump --opt -p%s -u%s' % (dbpass,dbuser)

# location of log directories
#logdir = '/var/log/pvarch'
logdir = '/home/newville/Codes/Epics/pva/logs'

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

######################################################
## Web setup section
##
apache_root = '/usr/local/apache/'
apache_root = '/www/apache/'
url_root    = 'http://ion.cars.aps.anl.gov/'

# location for python web scripts
cgi_bin   = apache_root  + 'cgi-bin/pvarch'

# how this maps to a URL:
cgi_url   = url_root     + 'cgi-bin/pvarch'

# location for output data files from PlotViewer
data_dir  = apache_root + 'htdocs/cgi-data/pvarch'

# how this maps to a URL:
data_url  = url_root    + 'cgi-data/pvarch'

# location for javascript calendar used by PlotViewer
jscal_dir  = apache_root + 'htdocs/cgi-data/jscal'

# how this maps to a URL:
jscal_url  = url_root    + 'cgi-data/jscal'

# title for status web pages
pagetitle = 'PV Archiver Status Page'

# footer for status web pages
footer = """<hr>[
<a href=http://www.aps.anl.gov/asd/blops/status/smallHistory.html>APS Storage Ring Status</a> |
<a href=http://www.aps.anl.gov/Facility/>APS Facility Page</a>]"""

# location of editable web status template files
#   the files in this directory should be readily editable
#   to customize the PVs displayed in the status page
#   directory needs to be world-readable, but can be in a user directory
template_dir  = '/usr/local/share/pvarch/templates/'
