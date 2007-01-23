dbuser   = 'epics'
dbpass   = 'epics'
dbhost   = 'localhost'
dblogdir = '/home/epics/logs'
mysqldump = '/usr/bin/mysqldump --opt -p%s -u%s' % (dbpass,dbuser)
