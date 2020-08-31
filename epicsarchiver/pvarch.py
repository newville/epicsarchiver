#!/usr/bin/env python3.8

# main pvarch application

import sys
import os
import time
from argparse import ArgumentParser

try:
    import epicsarchiver
except:
    print('cannot import epicsarchiver')
    sys.exit(1)

from epicsarchiver import Cache, Archiver, initial_sql
from epicsarchiver.util import tformat, get_config, MAX_EPOCH

def next_archive():
    master  = ArchiveMaster()
    old_dbname  = master.arch_db
    next_db = master.make_nextdb()

    master.stop_archiver()
    master.set_currentDB(next_db)

    master.close()
    run_archive(action='start')

def save_archives(args):
    " save archives to gzipped ascii files"
    m  = MasterDB()
    for db in (m.arch_db, master_db):
        m.save_db(dbname=db)
        if db in args: args.remove(db)

    for db in args:
        m.save_db(dbname=db)
    m.close()


def pvarch_main():
    parser = ArgumentParser(prog='pvarch',
                            description='control EpicsAarchiver processes',
                            add_help=False)
    parser.add_argument('-h', '--help', dest='help', action='store_true',
                        default=False, help='show help')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                        default=False, help='turn on debugging')
    parser.add_argument('-t', '--time_ago', dest='time_ago', type=int,
                        default=60, help='time for activity and status ')
    parser.add_argument('options', nargs='*')

    args = parser.parse_args()

    if args.help or len(args.options) == 0:
        print("""pvarch: control EpicsArchiver processes
    pvarch -h              shows this message.
    pvarch status [time]   shows cache and archiving status, some recent statistics. [60]

    pvarch start           start the archiving process, if it is not already running.
    pvarch stop            stop the archiving process
    pvarch restart         restart the archiving process

    pvarch next            create next archive database and restart archiving
    pvarch set_runinfo     set the run information for the most recent run
    pvarch list            prints a list of recent data archives
    pvarch save [folder]   save sql for cache and 2 most recent data archives [.]
    pvarch show_config     print configuration
    pvarch init [filename] write sql for initial setup of databases to file [pvarch_init.sql]

    pvarch unconnected_pvs show unconnected PVs in cache
    pvarch add_pv          add a PV to the cache and archive
    pvarch add_pvfile      read a file of PVs to add to the Archiver
    pvarch drop_pv         remove a PV from cahce and archive

    pvarch cache start     start cache process (if it is not already running)
    pvarch cache stop      stop cache process
    pvarch cache restart   restart cache process
    pvarch cache status    show cache status
    pvarch cache activity  show most recently updated PVs
    """)

        sys.exit()

    cmd = args.options.pop(0)

    ##
    ## the 'init' and 'show_config' commands may be run without a cache / archive database
    if cmd == 'init':
        if len(args.options) > 0:
            fname = args.options.pop(0)
        else:
            fname = 'pvarch_init.sql'
        config = get_config()
        sql = initial_sql(config)
        with open(fname, 'w') as fh:
            fh.write(sql)
        msg = """wrote initialization SQL statements to {fname:s}.  Use
   ~> mysql -p -u{user:s}  < {fname:s}"

to create initial databases.  Note that the mysql account '{user:s}'
will need to be able to create and modify databases. You may need to do
   mysql> create user '{user:s}'@'localhost' identified by 'a_password';
   mysql> grant all privileges on *.* to {user:s}@localhost;
   mysql> flush privileges;

as a mysql administrator.  Also, check that these settings match the
configuration file named in the environmental variable PVARCH_CONFIG.
""".format(fname=fname, user=config.user)
        print(msg)
        return

    elif cmd == 'show_config':
        msg = ["#pvarch configuration:"]
        if 'PVARCH_CONFIG' in os.environ:
            msg.append("#PVARCH_CONFIG='%s'" %os.environ['PVARCH_CONFIG'])
        else:
            msg.append("#No variable PVARCH_CONFIG found")

        for key, val in get_config().asdict().items():
            msg.append("%s = '%s'" % (key, val))
        msg.append('')
        print('\n'.join(msg))
        return

    ##
    ## the rest of the commands assume that a cache / archive database exist
    ##
    archiver = Archiver()
    cache = archiver.cache

    if 'status' == cmd:
        cache.show_status(cache_time=args.time_ago,
                          archive_time=args.time_ago)

    elif 'check' == cmd:
        print(cache.get_narchived(time_ago=args.time_ago))

    elif cmd == 'start':
        if len(cache.get_values(time_ago=15)) < 5:
               print("Warning: cache appears to not be running")
        if 5 < cache.get_narchived(time_ago=30):
            print("Archive appears to be running... try 'restart'?")
            return
        archiver.mainloop()

    elif cmd == 'stop':
        cache.set_info(process='archive', status='stopping')

    elif cmd == 'restart':
        cache.set_info(process='archive', status='stopping')
        time.sleep(2)
        archiver.mainloop()

    elif 'next' == cmd:
        cache.set_info(process='archive', status='stopping')
        time.sleep(1)
        cache.set_runinfo()
        new_dbname = cache.create_next_archive()

        # this requires remaking the Archiver and Cache as
        # the underlying DB engine is now altered.
        archiver = Archiver()
        runs = archiver.cache.tables['runs']
        runs.insert().execute(db=new_dbname, start_time=time.time(),
                              stop_time=MAX_EPOCH)
        archiver.cache.set_info(process='archive', db=new_dbname)
        time.sleep(1)
        archiver.mainloop()

    elif 'save' == cmd:
        if len(args.options) > 0:
            folder = args.options.pop(0)
        else:
            folder = '.'

        conf = get_config().asdict()
        conf['folder'] = os.path.abspath(folder)

        dbnames = [cache.db.dbname]
        runs = cache.get_runs()
        if len(runs) > 0:
            dbnames.append(runs[-1].db)
        if len(runs) > 1:
            dbnames.append(runs[-2].db)
        for dbname in dbnames:
            conf['dbname'] = dbname
            cmd = "{sql_dump:} -p{password:s} -u{user:s} {dbname:s} > {folder:s}/{dbname:s}.sql".format(**conf)
            os.system(cmd)
            print("wrote {folder:s}/{dbname:s}.sql".format(**conf))

    elif 'list' == cmd:
        runs = cache.tables['runs']
        hline = '+-----------------+-----------------------------------------------+'
        title = '|     database    |                date range                     |'
        out = [hline, title, hline]
        recent = runs.select().order_by(runs.c.id.desc()).limit(10)
        for run in recent.execute().fetchall():
            out.append('|  %13s  | %45s |' % (run.db, run.notes))
        out.append(hline)
        print('\n'.join(out))

    elif 'set_runinfo' == cmd:
        runs = cache.tables['runs']
        recent = runs.select().order_by(runs.c.id.desc()).limit(3)
        for run in recent.execute().fetchall():
            cache.set_runinfo(run.db)

    elif 'add_pv' == cmd:
        print(args.options)
        for pv in args.options:
            print("Add PV ", pv)
            cache.add_pv(pv)
        #
        # if len(args.options)>1:
        #    cache.set_allpairs(args.options)

    elif 'add_pvfile' == cmd:
        for pvfile in args.options:
            add_pvfile(pvfile)

    elif 'drop_pv' == cmd:
        for pvname in args.options:
            cache.drop_pv(pvname)

    elif 'unconnected_pvs' == cmd:
        print("checking for unconnected PVs in cache (may take several seconds)")
        c = Cache(pvconnect=True)
        time.sleep(0.01)
        unconn1 = []
        npvs = len(c.pvs)
        for pvname, pvobj in c.pvs.items():
            if not pvobj.connected:
                unconn1.append(pvname)

        # try again, waiting for connection:
        time.sleep(0.01)
        unconn = []
        for pvname in unconn1:
            c.pvs[pvname].connect(timeout=0.1)
            if not c.pvs[pvname].connected:
                unconn.append(pvname)

        print("# PVs in Cache that are currently unconnected:")
        for pvname in unconn:
            print('   %s' % pvname)

    elif 'cache' == cmd:
        action = None
        if len(args.options) > 0:
            action = args.options.pop(0)
        if action == 'status':
            cache.show_status(cache_time=args.time_ago, with_archive=False)

        elif action == 'activity':
            new_vals =cache.get_values(time_ago=args.time_ago, time_order=True)
            for row in new_vals:
                print("%s: %s = %s" % (tformat(row.ts), row.pvname, row.value))
            print("%3d new values in past %d seconds"%(len(new_vals), args.time_ago))

        elif action == 'start':
            if 5 < len(cache.get_values(time_ago=15)):
                print("Cache appears to be running... try 'restart'?")
                return
            cache = Cache(pvconnect=True, debug=args.debug)
            cache.mainloop()

        elif action == 'stop':
            cache.shutdown()
            time.sleep(1)

        elif action == 'restart':
            cache.shutdown()
            time.sleep(2)
            cache = Cache(pvconnect=True, debug=args.debug)
            cache.mainloop()

        else:
            print("'pvarch cache' needs one of start, stop, restart, status, activity")
            print("    Try 'pvarch -h' ")

    else:
        print("pvarch  unknown command '%s'.    Try 'pvarch -h'" % cmd)
