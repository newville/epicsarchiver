#!/usr/bin/env python
#

import sys
import MySQLdb
import os
import array
import time
from Queue import Queue, Empty, Full

import warnings
warnings.filterwarnings("ignore", "Unknown table.*")
warnings.filterwarnings("ignore", ".*drop database.*")
warnings.filterwarnings("ignore", ".*drop table.*")

from util import string_literal, clean_string, safe_string, clean_input

from config import master_db, dbuser, dbpass, dbhost, mysqldump

class Connection:
    def __init__(self,dbname=master_db,user=dbuser,passwd=dbpass,host=dbhost):
        self.conn = MySQLdb.connect(user=user, db=dbname, passwd=passwd,host=host)
        self.cursor = self.conn.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        
    def close(self):  self.conn.close()

class ConnectionPool(Queue):
    def __init__(self,constructor=Connection, size=32,out=None):
        Queue.__init__(self,size)
        self.constructor = constructor
        self.out = out
    def get(self,block=0,**kw):
        try:
            pstamp, obj = Queue.get(self,block)
            if (time.time() - pstamp) < 14400:
                if self.out is not None:
                    self.out.write("reuse dbconn: %s for PID=%i %s\n" % (repr(obj),os.getpid(),time.ctime()))
                    self.out.flush()
                return obj
            obj.close()
        except Empty:
            pass
        obj = self.constructor(**kw)
        if self.out is not None:
            self.out.write("create dbconn: %s for PID=%i %s\n" % (repr(obj),os.getpid(),time.ctime()))
            self.out.flush()
        return obj

    def put(self,obj, block=0):
        try:
            Queue.put(self,(time.time(),obj), block)
            if self.out is not None:
                self.out.write("return dbconn: %s for PID=%i %s\n" % (repr(obj),os.getpid(),time.ctime()))
                self.out.flush()
        except Full:
            pass

global cpool
cpool = ConnectionPool()

class SimpleTable:
    """ simple MySQL table wrapper class.
    Note: a table must have entry ID"""
    def __init__(self, table=None, db=None):
        self.db = db
        if db is  None:
            sys.stdout.write("Warning SimpleTable needs a database connection\n")
            return None

        self.fieldtypes = {}
        self._name  = None
        if table in self.db.table_list:
            self._name = table
        else:
            table = table.lower()
            if (table in self.db.table_list):
                self._name = table
            else:
                self.db.write("Table %s not available in %s " % (table,db))

                return None
        # sys.stdout.write( "ask to describe %s\n" % self._name)
        ret = self.db.exec_fetch("describe %s" % self._name)
        for j in ret:
            field = j['field'].lower()
            vtype = 'str'
            ftype = j['type'].lower()
            if ftype.startswith('int'):     vtype = 'int'
            if ftype.startswith('double'):  vtype = 'double'
            if ftype.startswith('float'):   vtype = 'float'
            self.fieldtypes[field] = vtype
            
    def check_args(self,**args):
        """ check that the keys of the passed args are all available
        as table columns.
        returns 0 on failure, 1 on success   """
        return self.check_columns(args.keys())

    def check_columns(self,l):
        """ check that the list of args are all available as table columns
        returns 0 on failure, 1 on success
        """
        for i in l:
            if not self.fieldtypes.has_key(i.lower()): return False
        return True
    
    def select_all(self):
        return self.select_where()

    def select_where(self,**args):
        """check for a table row, and return matches"""
        if (self.check_args(**args)):
            q = "select * from %s where 1=1" % (self._name)
            for k,v in args.items():
                k = clean_input(k)
                v = safe_string(v)
                q = "%s and %s=%s" % (q,k,v)
            # print 'S WHERE ', q
            return self.db.exec_fetch(q)
        return 0

    def select(self,vals='*', where='1=1'):
        """check for a table row, and return matches"""
        q= "select %s from %s where %s" % (vals, self._name, where)
        return self.db.exec_fetch(q)

    def select_one(self,vals='*', where='1=1'):
        """check for a table row, and return matches"""
        q= "select %s from %s where %s" % (vals, self._name, where)
        return self.db.exec_fetchone(q)

    def update(self,where='1=1', **kw): # set=None,where=None):
        """update a table row with set and where dictionaries:

           table.update_where({'x':1},{'y':'a'})
        translates to
           update TABLE set x=1 where y=a
           """
        if where==None or set==None:
            self.db.write("update must give 'where' and 'set' arguments")
            return
        try:
            s = []
            for k,v in kw.items():
                if self.fieldtypes.has_key(k):
                    ftype = self.fieldtypes[k]
                    k = clean_input(k)
                    if ftype == 'str':
                        s.append("%s=%s" % (k,safe_string(v)))
                    elif ftype in ('double','float'):
                        s.append("%s=%f" % (k,float(v)))
                    elif ftype == 'int':
                        s.append("%s=%i" % (k,int(v)))
            s = ','.join(s)
            q = "update %s set %s where %s" % (self._name,s,where)
            self.db.execute(q)
        except:
            self.db.write('update failed: %s' % q)

    def insert(self,**args):
        "add a new table row "
        ok = self.check_args(**args)
        if (ok == 0):
            self.db.write("Bad argument for insert ")
            return 0
        q  = []
        for k,v in args.items():
            if self.fieldtypes.has_key(k):
                ftype = self.fieldtypes[k]
                field = clean_input(k.lower())
                if (v == None): v = ''
                if isinstance(v,(str,unicode)):
                    v = safe_string(v)
                else:
                    v = str(v)
                # v =clean_input(v,maxlen=flen)
                q.append("%s=%s" % (field, v))
        s = ','.join(q)
        qu = "insert into %s set %s" % (self._name,s)
        self.db.execute(qu)
        

    def __repr__(self):
        """ shown when printing instance:
        >>>p = Table()
        >>>print p
        """
        return "<MyTable name=%s>" % ( self._name )

class SimpleDB:
    """ Wrapper for MySQL database, using SimpleTable class"""
    message_types= {'normal': '',
                    'warning': 'Warning: ',
                    'error': 'Error: ',
                    'fatal': 'Fatal Error: '}

    SimpleDB_Exception = 'Simple DB Exception'
    def __init__(self, dbconn=None,
                 dbname=None, user=None, passwd=None, host=None,
                 debug=0, messenger=None,bindir=None,autocommit=1):
        

        self.debug     = debug
        self.messenger = messenger or sys.stdout
        self.user      = user      or dbuser
        self.passwd    = passwd    or dbpass
        self.host      = host      or dbhost
        self.dbname    = dbname    or master_db
        self.autocommit= autocommit
        self.tables = []
        # start mysql connection
        self.cursor = None
        self.conn   = None
        self.get_cursor(dbconn=dbconn)
        self.set_autocommit(autocommit)

        self.read_table_info()

    def __repr__(self):
        """ shown when printing instance:
        >>>p = Table()
        >>>print p
        """
        return "<SimpleDB name=%s>" % (self.dbname)

    def get_cursor(self,dbconn=None):
        " get a DB cursor, possibly getting a new one from the Connection pool"

        if self.conn is not None:
            if self.cursor is None:   self.cursor = self.conn.cursor
            return self.cursor

        # try the one provided or get a new connection from the pool
        self.conn = dbconn
        conn_count = 0
        while self.conn is None and conn_count < 100:
            try: 
                self.conn =  cpool.get(user=self.user,
                                       dbname=self.dbname,
                                       passwd=self.passwd,
                                       host=self.host)
            except:
                time.sleep(0.010)
                conn_count = conn_count + 1
                
        if self.conn is None:
            self.write("Could not start MySQL on %s for database %s" %
                       (self.host, self.dbname),   status='fatal')
            raise IOError, "no database connection to  %s" %  self.dbname

        self.cursor = self.conn.cursor
        return self.cursor
    
    def set_autocommit(self,commit=1):
        self.get_cursor()
        # sys.stdout.write(" set autocommit %i /cursor = %s \n" % (commit,repr(self.cursor)))
        self.cursor.execute("set AUTOCOMMIT=%i" % commit)        

    def begin_transaction(self):
        self.get_cursor()        
        self.cursor.execute("start transaction")

    def commit_transaction(self):
        self.get_cursor()
        self.cursor.execute("commit")

    def put_cursor(self):
        " return a cursor to the Connection pool"        
        if self.cursor is not None:
            # sys.stdout.write('releasing cursor\n')
            cpool.put(self.conn)
            self.cursor = None

    def close(self):
        " close db connection"
        self.put_cursor()
        
    def safe_dump(self, file=None,compress=False):
        " dump database to file with mysqldump"
        if (file==None): file = "%s.sql" % self.dbname
        cmd = "%s %s > %s" % (mysqldump, self.dbname, file)
        try:
            os.system("%s" % (cmd))
        except:
            self.write("could not dump database '%s' to file '%s'" % (self.dbname,file))            
        if compress:
            try:
                os.system("gzip -f %s" % (file))
            except:
                self.write("could not compress database file %s" % (file))

    def write(self, msg,status='normal'):
        " write message, with status "
        if (status not in self.message_types.keys()): status = 'normal'
        
        self.messenger.write("## %s%s\n" % (self.message_types[status], msg))
        if (status ==  'fatal'):
            raise IOError, msg
       
    def source_file(self,file=None,report=100):
        """ execute a file of sql commands """
        self.get_cursor()
        try:
            f = open(file)
            lines = f.readlines()
            count = 0
            cmds = []
            for x in lines:
                if not x.startswith('#'):
                    x = x[:-1].strip()
                    if x.endswith(';'):
                        cmds.append(x[:-1])
                        sql = "".join(cmds)
                        self.__execute(sql)
                        cmds = []
                    else:
                        cmds.append(x)
                count = count +1
                if (report>0 and (count % report == 0)):
                    self.write("%i / %i " % (count,len(lines)))
            f.close()
        except:
            self.write(" could not source file %s" % file)
      
    def clean_string(self, s):    return clean_string(s)
    def string_literal(self, s):  return string_literal(s)

    def use(self,dbname):
        " use database, populate initial list of tables -- may create a cursor!"
        self.dbname  = dbname
        self.get_cursor()
        self.__execute("use %s" % dbname)
        
    def read_table_info(self):
        " use database, populate initial list of tables "
        self.get_cursor()
        self.table_list = []
        self.tables     = {}
        x = self.exec_fetch("show TABLES")
        # print 'Read Table Info ', x
        self.table_list = [i.values()[0] for i in x]
        for i in self.table_list:
            self.tables[i] = SimpleTable(i,db=self)
         
    def execute(self,q):
        "execute a single sql command string or a tuple or list command strings"
        if self.cursor is None: self.get_cursor()
        ret = None
        if isinstance(q,str):
            ret = self.__execute(q)
        elif isinstance(q,(list,tuple)):
            ret = [self.__execute(i) for i in q]
        else:
            self.write("Error: could not execute %s" % str(qlist))
        return ret

    def __execute(self,q):
        """internal execution of a single query -- needs a valid cursor!"""
        
        if self.cursor is None: self.get_cursor()            
        if self.cursor is None:
            self.write("SimpleDB.__execute -- no cursor: %s" % q)
            sys.exit(1)
        n = 0
        while n < 50:
            n = n + 1
            try:
                return self.cursor.execute(q)
            except:
                time.sleep(0.010)
        self.write("Query Failed: %s " % (q))
        return None

            
    def _normalize_dict(self, indict):
        """ internal 'normalization' of query outputs,
        converting unicode to str and array data to lists"""
        t =  {}
        if self.debug==1: sys.stdout.write( '_normalize dict: ')
        if (indict == None): return t
        for k,v in indict.items():
            key = k.lower()
            val = v
            if isinstance(v,array.array):
                if v.typecode == 'c':
                    val = v.tostring()
                else:
                    val = v.tolist()
            elif isinstance(v,unicode):
                val = str(v)
            t[key] = val
        return t
    
    def fetchone(self):
        "return next row from most recent query -- needs valid cursor"
        if self.cursor is None: return {}
        return self._normalize_dict(self.cursor.fetchone())
 
    def fetchall(self):
        "return all rows from most recent query -- needs valid cursor"
        if self.cursor is None: return ()
        r = [self._normalize_dict(i) for i  in self.cursor.fetchall()]
        return tuple(r)

    def exec_fetch(self,q):
        " execute + fetchall"
        self.get_cursor()
        self.__execute(q)
        ret = self.fetchall()
        return ret
    
    def exec_fetchone(self,q):
        " execute + fetchone"
        self.get_cursor()
        self.__execute(q)
        ret = self.fetchone()
        return ret

    def create_and_use(self, dbname):
        "create and use a database.  Use with caution!"
        self.get_cursor()
        self.__execute("drop database if exists %s" % dbname)
        self.__execute("create database %s" % dbname)
        self.use(dbname)

    def grant(self,db=None,user=None,passwd=None,host=None,priv=None,grant=False):
        """grant permissions """
        if db     is None: db  = self.dbname
        if user   is None: user = self.user 
        if passwd is None: passwd = self.passwd 
        if host   is None: host = self.host
        if priv   is None: priv = 'all privileges'
        priv = clean_input(priv)
        grant_opt =''
        if grant: grant_opt = "with GRANT OPTION"
        self.get_cursor()
        
        cmd = "grant %s on %s.* to %s@%s identified by '%s'  %s" 
        self.__execute(cmd % (priv,db,user,host,passwd,grant_opt) )

