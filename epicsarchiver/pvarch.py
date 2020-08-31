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

from epicsarchiver import Cache, Archiver, tformat

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

def clean_web_datafiles():
    """clean old files from web data / plot directory:
    files older than 2 days will be deleted"""
    now = time.time()
    nclean = 0
    for i in os.listdir(data_dir):
        fname = os.path.abspath(os.path.join(data_dir,i))
        if (os.path.isfile(fname) and i.startswith(webfile_prefix)):
            mtime = os.stat(fname)[8]
            if (now - mtime) > 2*SEC_DAY:
                os.unlink(fname)
                nclean = nclean+1
    print('removed %i files from %s' % (nclean,data_dir))


def drop_pv(a, pvname):
    a.cache.drop_pv(pvname)

def start_archiver(a, force=False):
    if not force:
        nchanged  = cache.get_narchvived(time_ago=30)
        if nchanged > 5:
            print("Archive appears to be running... try 'restart'?")
            return
    a.mainloop()

def start_cache(a, force=False):
    if not force:
        nchanged  = a.cache.get_values(time_ago=15)
        if nchanged > 5:
            print("Cache appears to be running... try 'restart'?")
    a.cache.mainloop()
        
        
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
    pvarch -h            shows this message.
    pvarch status        shows cache and archiving status, some recent statistics.
    pvarch check         print # of archivedsin past 10 minutes. Should be >1!

    pvarch start         start the archiving process
    pvarch stop          stop the archiving process
    pvarch restart       restart the archiving process
    pvarch next          restart with 'next run' of data archives
    pvarch setinfo       set the run information for the most recent run

    pvarch add_pv        add a PV to the cache and archive
    pvarch add_pvfile    read a file of PVs to add to the Archiver
    pvarch drop_pv       remove a PV from cahce and archive

    pvarch list          prints a list of recent data archives
    pvarch save          save a list of recent data archives

    pvarch cache start        start cache process (if it's not already running)
           cache stop         stop  cache process
           cache status       show cache status
           cache activity     show detailed cache activitiy
    """)

        sys.exit()
          
    archiver = Archiver()
    cache = archiver.cache

    cmd = args.options.pop(0)

    if 'status' == cmd:
        cache.show_status(cache_time=args.time_ago,
                          archive_time=args.time_ago)

    elif 'check' == cmd:
        print(cache.get_narchived(time_ago=args.time_ago))

    elif cmd == 'start':
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
        cache.next_archive()
        time.sleep(5)
        archiver = Archiver()
        archiver.mainloop()
        print("should now run 'pvarch setinfo'")

    elif 'save' == cmd:
        save_archives(args)

    elif 'list' == cmd:
        runs = cache.tables['runs']
        hline = '|----------------|--------------------------------------------|'
        title = '|  database      |                date range                  |'
        out = [hline, title, hline]
        recent = runs.select().order_by(runs.c.id.desc()).limit(10)
        for run in recent.execute().fetchall():
            out.append('|  %12s  | %s |' % (run.db, run.notes))
            out.append(hline)
        print('\n'.join(out))

    elif 'setinfo' == cmd:
        runs = cache.tables['runs']
        recent = runs.select().order_by(runs.c.id.desc()).limit(3)
        for run in recent.execute().fetchall():
            cache.set_runinfo(run.db)

    elif 'add_pv' == cmd:
        for pv in args:
            cache.add_pv(pv)
        if len(args)>1:
            cache.set_allpairs(args)

    elif 'add_pvfile' == cmd:
        for pvfile in args:
            add_pvfile(pvfile)

    elif 'drop_pv' == cmd:
        for pv in args:
            cache.drop_pv(pv)

    elif 'cache' == cmd:
        action = args.options.pop(0)

        if action not in ('start','stop','restart', 'activity', 'status'):
            print("'pvarch cache' needs one of start, stop, restart, status, activity")
            print("    Try 'pvarch -h' ")

        elif action == 'status':
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

        elif action == 'restart':
            cache.get_values(time_ago=time_ago)
            
            time.sleep(2)
            cache = Cache(pvconnect=True, debug=args.debug)
            cache.mainloop()

    else:
        print("pvarch  unknown command '%s'.    Try 'pvarch -h'" % cmd)

