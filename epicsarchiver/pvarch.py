#!/usr/bin/env python3

# main pvarch application

import os
import time
import toml
import subprocess
from pathlib import Path
from argparse import ArgumentParser
from tabulate import tabulate

from . import Cache, Archiver, tformat, get_config
from .schema import initial_sql, apache_config

HELP_MESSAGE = """pvarch: control EpicsArchiver processes
    pvarch -h              shows this message.
    pvarch status [-t time] shows cache and archiving status, some recent statistics. [60]
    pvarch show_config     print configuration

    pvarch arch start      start the archiving process, if it is not already running.
    pvarch arch stop       stop the archiving process
    pvarch arch restart    restart the archiving process
    pvarch arch next       create next archive database and restart archiving

    pvarch cache start     start cache process (if it is not already running)
    pvarch cache stop      stop cache process
    pvarch cache restart   restart cache process
    pvarch cache status    show cache status
    pvarch cache activity  show most recently updated PVs

    pvarch list    [n]     prints a list of recent data archives  [10]
    pvarch set_runinfo [n] set the run information for the most recent run [10]
    pvarch save [folder] [n]  save sql for cache and most recent data archives(s) [., 1]
    pvarch save_zarr [n]   save zarray zip file for recent, not-current data archives(s) [1]

    pvarch unconnected_pvs show unconnected PVs in cache
    pvarch add_pv          add a PV to the cache and archive
    pvarch add_pvfile      read a file of PVs to add to the Archiver
    pvarch drop_pv         remove a PV from cahce and archive

    pvarch sql_init [filename] write sql for initial setup of databases to file [pvarch_init.sql]
    pvarch web_init [filename] write apache config file and stub wsgi app [pvarch.conf/pvarch.wsgi]

"""

SQL_INIT_MESSAGE = """wrote initialization SQL statements to '{fname:s}'.  Use
   ~> mysql -p -u{user:s}  < {fname:s}"

to create initial databases.  Note that the mysql account '{user:s}'
will need to be able to create and modify databases. You may need to do
   mysql> create user '{user:s}'@'localhost' identified by 'lets_archive_some_pvs';
   mysql> grant all privileges on *.* to '{user:s}'@'localhost';
   mysql> flush privileges;

as a mysql administrator.  Also, check that these settings match the
configuration file named in the environmental variable EPICSARCH_CONFIG.
"""

WEB_INIT_MESSAGE = """
wrote intial apache config to '{fname:s}', and web configuration
file to 'wsgi/config.toml'

You will need to install these for your webserver by:

1. copy the full wsgi folder to '{web_dir:s}', as with

   ~> cp -pr wsgi/*  {web_dir:s}/.

2. include '{fname:s}' in your apache config, as with

    ~> cp -pr {fname:s} {server_root:s}/conf.d/.

   then adding

      IncludeOptional {server_root:s}/conf.d/{fname:s}

   to your main apache 'httpd.conf' file and restarting the httpd service.

"""

DUMP_COMMAND = "{sql_dump:} -p{password:s} -u{user:s} {dbname:s} > {folder:s}/{dbname:s}.sql"


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
    parser.add_argument('-n', '--nruns', dest='nruns', type=int,
                        default=0, help='number of runs for list and set_runinfo')
    parser.add_argument('options', nargs='*')

    args = parser.parse_args()

    ## 'help', 'init', and 'show_config' commands may be
    ## run without a cache / archive database
    if args.help or len(args.options) == 0:
        print(HELP_MESSAGE)
        return

    cmd = args.options.pop(0)

    if cmd == 'sql_init':
        if len(args.options) > 0:
            fname = args.options.pop(0)
        else:
            fname = 'pvarch_init.sql'
        config = get_config()
        sql = initial_sql(config)
        if not fname.endswith('.sql'):
            fname = "%s.sql" % fname
        with open(fname, 'w') as fh:
            fh.write(sql)
        print(SQL_INIT_MESSAGE.format(fname=fname, user=config.user))
        return

    elif cmd == 'web_init':
        if len(args.options) > 0:
            fname = args.options.pop(0)
        else:
            fname = 'pvarch'
        config = get_config().asdict()
        if not fname.endswith('.conf'):
            fname = "%s.conf" % fname

        s_root = '<your httpd root>'
        try:
            lines = os.popen('apachectl -S').readlines()
        except:
            lines = []
        for line in lines:
            if line.startswith('ServerRoot:'):
                s_root = line[:-1]
                for x in ('ServerRoot:', '"', "'"):
                    s_root = s_root.replace(x, '')
                s_root = s_root.strip()
        config['server_root'] = s_root
        with open(fname, 'w') as fh:
            fh.write(apache_config.format(**config))
        if Path('wsgi').exists():
            cfile = Path('wsgi', 'config.toml').absolute().as_posix()
            with open(cfile, 'w') as fh:
                toml.dump(config, fh)

        print(WEB_INIT_MESSAGE.format(fname=fname, **config))
        return

    elif cmd == 'show_config':
        msg = ["#pvarch configuration:"]
        if 'EPICSARCH_CONFIG' in os.environ:
            msg.append("#EPICSARCH_CONFIG='%s'" %os.environ['EPICSARCH_CONFIG'])
        else:
            msg.append("#No variable EPICSARCH_CONFIG found")

        for key, val in get_config().asdict().items():
            msg.append("%s = '%s'" % (key, val))
        msg.append('')
        print('\n'.join(msg))
        return

    ## the rest of the commands assume that a cache / archive database exist
    archiver = Archiver()
    cache = archiver.cache
    config = get_config().asdict()

    if 'status' == cmd:
        cache.show_status(cache_time=args.time_ago,
                          archive_time=args.time_ago)

    elif 'check' == cmd:
        print(cache.get_narchived(time_ago=args.time_ago))

    elif cmd == 'arch':
        action = None
        if len(args.options) > 0:
            action = args.options.pop(0)
        if action == 'start':
            cache_tago = int(config.get('cache_activity_time', '10'))
            cache_nmin = int(config.get('cache_activity_min_updates', '2'))
            if len(cache.get_values(time_ago=cache_tago)) < cache_nmin:
                print("Warning: cache appears to not be running")

            arch_tago = int(config.get('arch_activity_time', '60'))
            arch_nmin = int(config.get('arch_activity_min_updates', '2'))
            if cache.get_narchived(time_ago=arch_tago) > arch_nmin:
                print("Archive appears to be running... try 'restart'?")
                return
            archiver.mainloop()

        elif action == 'stop':
            cache.set_info(process='archive', status='stopping')

        elif action == 'restart':
            cache.set_info(process='archive', status='stopping')
            time.sleep(2)
            archiver.mainloop()

        elif action == 'next':
            new_dbname = cache.create_next_archive()
            print("Created New DB ", new_dbname)
            cache.set_info(process='archive', status='stopping')
            time.sleep(1)
            # cache.set_runinfo()
            cache.set_info(process='archive', db=new_dbname)
            time.sleep(1)
            # this requires remaking the Archiver and Cache as
            # the underlying DB engine is now altered.
            archiver = Archiver()
            time.sleep(1)
            archiver.mainloop()

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
            cache_tago = int(config.get('cache_activity_time', '10'))
            cache_nmin = int(config.get('cache_activity_min_updates', '2'))
            if len(cache.get_values(time_ago=cache_tago)) > cache_nmin:
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

    elif 'save' == cmd:
        folder = '.'
        nruns = 1
        if len(args.options) > 0:
            folder = args.options.pop(0)
        if len(args.options) > 1:
            nruns = args.options.pop(1)

        dbnames = [cache.db.dbname]
        dbnames.extend([run.db for run in cache.get_runs()[-nruns:]])

        zarr_folder = Path(config['zarrdir']).absolute().as_posix()
        
        sqldump = '{sql_dump:} -p{password:s} -u{user:s}'.format(**config)
        for dbname in dbnames:
            cmds = f'{sqldump} {dbname}'.split()
            outfile = Path(folder, f'{dbname}.sql').absolute().as_posix()
            subprocess.run(cmds, stdout=open(outfile, 'w'))
            subprocess.run(['gzip', '-f', outfile])

    elif 'save_zarr' == cmd:
        nruns = 1
        if len(args.options) > 0:
            nruns =int(args.options.pop(0))

        dbnames = [run.db for run in cache.get_runs()[-(nruns+5):]]
        
        zarr_folder = Path(config['zarrdir']).absolute()
        
        if not zarr_folder.exists():
            print(f"Zarr folder does not exist: {config['zarrdir']}")
        else:
            nsaved = 0
            for dbname in reversed(dbnames):
                if dbname == archiver.dbname:
                    continue                
                archiver.save_zarr(dbname)
                nsaved += 1
                #except:
                #    print(f"Could not save zarr file for {dbname} to {config['zarrdir']}")
                if nsaved >= nruns:
                    break
                    
            
    elif 'list' == cmd:
        nruns = args.nruns
        if nruns == 0:
            nruns = 25
        runs = cache.tables['runs']
        out = [['database', 'date range']]
        recent = cache.db.get_rows('runs', order_by='id', order_desc=True)
        for run in reversed(recent[:nruns]):
            out.append([run.db, run.notes])
        print(tabulate(out, headers='firstrow', tablefmt='simple_grid'))

    elif 'set_runinfo' == cmd:
        nruns = args.nruns
        if nruns == 0:
            nruns = 2
        recent = cache.db.get_rows('runs', order_by='id', order_desc=True)
        for run in reversed(recent[:nruns]):
            cache.set_runinfo(run.db)

    elif cmd in ('add_pv', 'add_pvfile', 'drop_pv', 'unconnected_pvs'):
        # these commands need a Cache that has connected to Epics PVs
        cache = Cache(pvconnect=True, debug=args.debug)
        if 'add_pv' == cmd:
            for pv in args.options:
                cache.add_pv(pv)
                if len(args.options)>1:
                    cache.set_allpairs(args.options)

        elif 'add_pvfile' == cmd:
            for pvfile in args.options:
                cache.add_pvfile(pvfile)

        elif 'drop_pv' == cmd:
            for pvname in args.options:
                cache.drop_pv(pvname)

        elif 'unconnected_pvs' == cmd:
            print("checking for unconnected PVs in cache (may take several seconds)")
            time.sleep(0.01)
            unconn1 = []
            npvs = len(cache.pvs)
            for pvname, pvobj in cache.pvs.items():
                if not pvobj.connected:
                    unconn1.append(pvname)

            # try again, waiting for connection:
            time.sleep(0.01)
            unconn = []
            for pvname in unconn1:
                cache.pvs[pvname].connect(timeout=0.1)
                if not cache.pvs[pvname].connected:
                    unconn.append(pvname)

            print("# PVs in Cache that are currently unconnected:")
            for pvname in unconn:
                print('   %s' % pvname)

    else:
        print("pvarch  unknown command '%s'.    Try 'pvarch -h'" % cmd)
