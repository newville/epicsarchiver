#!/usr/bin/env python

"""
    This module is used to fork the current process into a daemon.
    Almost none of this is necessary (or advisable) if your daemon 
    is being started by inetd. In that case, stdin, stdout and stderr are 
    all set up for you to refer to the network connection, and the fork()s 
    and session manipulation should not be done (to avoid confusing inetd). 
    Only the chdir() and umask() steps remain as useful.
    References:
        UNIX Programming FAQ
            1.7 How do I get my program to act like a daemon?
                http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        Advanced Programming in the Unix Environment
            W. Richard Stevens, 1992, Addison-Wesley, ISBN 0-201-56317-7.

    History:
      2001/07/10 by J?rgen Hermann
      2002/08/28 by Noah Spurrier
      2003/02/24 by Clark Evans
      
      http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66012
"""
import sys, os, time
from signal import SIGTERM

def daemonize(stdout='/dev/null', stderr=None, stdin='/dev/null',
              pidfile=None,
              startmsg = 'started with pid %s',
              func = None, *args, **kws):
    """
        This forks the current process into a daemon, then runs the supplied
        function in that daemon process.
        
        The stdin, stdout, and stderr arguments are file names that
        will be opened and be used to replace the standard file descriptors
        in sys.stdin, sys.stdout, and sys.stderr.
        These arguments are optional and default to /dev/null.
        Note that stderr is opened unbuffered, so
        if it shares a file with stdout then interleaved output
        may not appear in the order that you expect.
    """
    if stderr is None: stderr = stdout

    # Do first fork.
    try: 
        pid = os.fork() 
        if pid > 0: sys.exit(0) # Exit first parent.
    except OSError, e: 
        sys.stderr.write("fork #1 failed: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)
        
    # Decouple from parent environment.
    os.chdir("/") 
    os.umask(0) 
    os.setsid() 
    
    # Do second fork.
    try: 
        pid = os.fork() 
        if pid > 0: sys.exit(0) # Exit second parent.
    except OSError, e: 
        sys.stderr.write("fork #2 failed: (%d) %s\n" % (e.errno, e.strerror))
        sys.exit(1)
    
    # Open file descriptors and print start message
    si = file(stdin, 'r')
    so = file(stdout, 'w+')
    se = file(stderr, 'w+', 0)
    pid = str(os.getpid())
    sys.stderr.write("\n%s\n" % startmsg % pid)
    sys.stderr.flush()
    if pidfile: file(pidfile,'w+').write("%s\n" % pid)
    
    # Redirect standard file descriptors.
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    if callable(func): func(*args,**kws)
    
def startstop(stdout='/dev/null', stderr=None, stdin='/dev/null',
              process_name = '',   pidfile='pid.txt',
              startmsg = 'started with pid %s',
              action='start',func=None,**kws):

    fname = ''
    if callable(func): fname = "(%s)" % func.__name__
    if action not in ('start','stop','restart','status'):
        print "startstop: %s %s start|stop|restart|status" % (process_name,fname)
        sys.exit(2)        
    try:
        pf  = file(pidfile,'r')
        pid = int(pf.read().strip())
        pf.close()
    except:
        pid = None
    #
    # see if pid is live (from /proc/PID/io)
    pid_status='unknown'
    if pid:
        try:
            procio_file = file('/proc/%i/io' % pid,'r')
            l  = procio_file.readlines()
            if len(l) > 1: pid_status = 'alive'
        except IOError:
            pid_status = 'not running'            
            
    if action in ('stop','restart'):
        if not pid:
            mess = "Warning: Could not stop, pid file '%s' missing.\n"
            sys.stderr.write(mess % pidfile)
            if 'restart' == action: action = 'start'
            pid = None
        else:
            try:
               while 1:
                   os.kill(pid,SIGTERM)
                   time.sleep(0.5)
            except OSError, err:
               err = str(err)
               if err.find("No such process") > 0:
                   os.remove(pidfile)
                   if 'retart' == action: action = 'start'
                   pid = None
               else:
                   print str(err)
                   sys.exit(1)
    if 'status' == action:
        msg = 'running'
        if not pid: msg = 'stopped'
        sys.stderr.write("status for %s %s: %s\n" % (process_name,fname,msg))
    if 'start' == action:
        if pid and pid_status == 'alive':
            mess = " Process ID=%i (found from file '%s') is running.\n Try 'restart?'\n"
            sys.stderr.write(mess % (pid,pidfile))
        else:
            daemonize(stdout,stderr,stdin,pidfile,startmsg,func=func,**kws)
    return
        

def test():
    """ This is an example main function run by the daemon.
        This prints a count and timestamp once per second."""

    sys.stdout.write ('Message to stdout...')
    sys.stderr.write ('Message to stderr...')
    c = 0
    while 1:
        sys.stdout.write ('%d: %s\n' % (c, time.ctime(time.time())) )
        sys.stdout.flush()
        c = c + 1
        time.sleep(1)


def test2(name='bob'):
    sys.stdout.write ('Message to stdout...')
    sys.stderr.write ('Message to stderr...')
    while 1:
        sys.stdout.write ('%s: %s\n' % (name, time.ctime(time.time())) )
        sys.stdout.flush()
        time.sleep(2)


if __name__ == "__main__":
    args= sys.argv
    args.append(None)

    print args
    startstop(stdout='/tmp/daemon1.log',  pidfile='/tmp/daemon1.pid',
              process_name = args[0],   action=args[1], func=test)
    
    
