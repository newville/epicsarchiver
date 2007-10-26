#!/usr/bin/env python
#

try:
    import MySQLdb
except ImportError:
    import os
    os.environ['PYTHON_EGG_CACHE'] = '/tmp/python_eggs/'
    import MySQLdb
except ExtractionError:
    import os
    os.environ['PYTHON_EGG_CACHE'] = '/tmp/python_eggs/'
    import MySQLdb
    

import sys
import os
import array
import time
import types

import warnings
warnings.filterwarnings("ignore", "Unknown table.*")
warnings.filterwarnings("ignore", ".*drop database.*")

from util import string_literal, safe_string, clean_input, clean_string
import config

def db_connect(dbname='test',
               user=config.dbuser,
               passwd=config.dbpass,
               host=config.dbhost,
               autocommit=1):
    return SimpleDB(dbname=dbname,user=user, passwd=passwd,
                    host=host, autocommit=autocommit)

def save_db(dbname=None,compress=True):
    if dbname is not None:
        db = db_connect(dbname=dbname)
        db.use(dbname)
        db.safe_dump(compress=compress)
        
class SimpleTable:
    """ simple MySQL table wrapper class.
    Note: a table must have entry ID"""

    def __init__(self,db, table=None):
        self.db = db
        if db == None:
            sys.stdout.write("Warning SimpleTable needs a database\n")
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

        # print "done: describe %s" % self._name
        for j in self.db.exec_fetch("describe %s" % self._name):
            field = j['field'].lower()
            vtype = 'str'
            ftype = j['type'].lower()
            if ftype.startswith('int'):   vtype = 'int'
            if ftype.startswith('double'): vtype = 'double'            
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
    
    def delete_where(self,**args):
        """delete row: NOT """
        if (self.check_args(**args)):
            q = "delete from %s where 1=1" % (self._name)
            for k,v in args.items():
                k = clean_input(k)
                v = string_literal(v)
                q = "%s and %s=%s" % (q,k,v)
            # print 'DELETE WHERE: ', q
            # return self.db.exec_fetch(q)
        return 0

    def select_all(self):
        return self.select_where()

    def select_where(self,**args):
        """check for a table row, and return matches"""
        if (self.check_args(**args)):
            q = "select * from %s where 1=1" % (self._name)
            for k,v in args.items():
                k = clean_input(k)
                v = string_literal(v)
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
        if True: # try:
            s = []
            if self.check_columns(kw.keys()):
                for k,v in kw.items():
                    k = clean_input(k)
                    v = clean_input(v)
                    if 'str' == self.fieldtypes[k]:
                        s.append("%s=%s" % (k,safe_string(v)))
                    elif 'double' == self.fieldtypes[k]:
                        s.append("%s=%f" % (k,float(v)))
                    elif 'int' == self.fieldtypes[k]:
                        s.append("%s=%i" % (k,int(v)))
            s = ','.join(s)
            q = "update %s set %s where %s" % (self._name,s,where)
            self.db.execute(q)
        else: # except:
            self.db.write('update failed ')
            self.db.write("##q = %s" % q)
        return self.db.affected_rows()

    def insert(self,**args):
        "add a new table row "
        ok = self.check_args(**args)
        if (ok == 0):
            self.db.write("Bad argument for insert ")
            return 0
        q  = []
        for k,v in args.items():
            field = clean_input(k.lower())
            if (v == None): v = ''
            if type(v) == types.StringType:
                v = safe_string(v)
            else:
                v = str(v)
            q.append("%s=%s" % (field, v))
        s = ','.join(q)
        qu = "insert into %s set %s" % (self._name,s)
        # print 'insert: ', qu
        self.db.execute(qu)
        return self.db.affected_rows()

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
    def __init__(self,dbname=None, user=None, passwd=None, host=None,
                 debug=0, messenger=None,bindir=None,autocommit=1):
        

        self.debug     = debug
        self.messenger = messenger or sys.stdout
        self.user      = user      or config.dbuser
        self.passwd    = passwd    or config.dbpass
        self.host      = host      or config.dbhost
        self.dbname    = dbname    or 'test'

        self.tables = []
        # start mysql connection
        try:
            self.db   = MySQLdb.connect(user=self.user,
                                        db=self.dbname,
                                        passwd=self.passwd,
                                        host=self.host)
        except:
            self.write("Could not start MySQL on %s for database %s" %
                       (self.host, self.dbname),   status='fatal')
            
        self.cursor = self.db.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        
        self.use(self.dbname)
        self.__execute("set AUTOCOMMIT=%i" % autocommit)
        self.read_table_info()

    def close(self):
        " close db connection"
        self.cursor = 0
        self.db.close()
        
    def safe_dump(self, file=None,compress=False):
        " dump database to file with mysqldump"
        if (file==None): file = "%s.sql" % self.dbname
        cmd = "%s %s > %s" % (config.mysqldump, self.dbname, file)
        try:
            os.system("%s" % (cmd))
        except:
            msg = "could not dump database '%s' to file '%s'"
            self.write(msg % (self.dbname,file))            
        if compress:
            try:
                os.system("gzip -f %s" % (file))
            except:
                self.write("could compress database file %s" % (file))

    def write(self, msg,status='normal'):
        " write message, with status "
        if (status not in self.message_types.keys()): status = 'normal'
        
        self.messenger.write("## %s%s\n" % (self.message_types[status], msg))
        if (status ==  'fatal'):
            raise IOError, msg
       
    def source_file(self,file=None,report=100):
        """ execute a file of sql commands """
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

    def clean_string(self, s):   return clean_string(s)
    def string_literal(self, s):  return string_literal(s)

    def use(self,db):
        " use database, populate initial list of tables "
        self.dbname  = db
        self.__execute("use %s" % db)

    def read_table_info(self):
        " use database, populate initial list of tables "
        self.table_list = []
        self.tables     = {}
        x = self.exec_fetch("show TABLES")
        self.table_list = [i.values()[0] for i in x]
        for i in self.table_list:
            self.tables[i] = SimpleTable(self,table=i)

    def execute(self,qlist):
        "execute a single sql command string or a tuple or list command strings"
        if isinstance(qlist,str): return self.__execute(qlist)
        if isinstance(qlist,tuple) or isinstance(qlist,list):
            r = []
            for q in qlist: r.append( self.__execute(q))
            return r
        self.write("Error: could not execute %s" % str(qlist) )
        return None                                      
        
    def __execute(self,q):
        """internal execution of a single query
        If the execution fails, it is tried again, and then gives up"""
        try:
            if (self.debug == 1): sys.stdout.write( "SQL> %s\n" % (q))
            return self.cursor.execute(q)
        except:
            time.sleep(0.050)
            try:
                if (self.debug == 1): sys.stdout.write( "SQL(repeat)> %s\n" % (q))
                return self.cursor.execute(q)
            except:
                self.write("SQL Query Failed: %s " % (q))
        return None
            
    def fetchone(self):
        "return next row from most recent query"
        return self._normalize_dict(self.cursor.fetchone())
 
    def affected_rows(self):
        "return number  of rows affected by last execute"
        try:
            return self.cursor.rowcount()
        except:
            return self.db.affected_rows()

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
    
    def fetchall(self):
        "return all rows from most recent query"
        r = [self._normalize_dict(i) for i  in self.cursor.fetchall()]
        return tuple(r)

    def exec_fetch(self,q):
        " execute + fetchall"
        self.__execute(q)
        return self.fetchall()

    def exec_fetchone(self,q):
        " execute + fetchone"
        self.__execute(q)
        return self.fetchone()

    def create_and_use(self, dbname):
        "create and use a database.  Use with caution!"
        self.__execute("drop database if exists %s" % dbname)
        self.__execute("create database %s" % dbname)
        self.use(dbname)

    def grant(self,db=None,user=None,passwd=None,host=None,priv=None):
        """grant permissions """
        if db     is None: db  = self.dbname
        if user   is None: user = self.user 
        if passwd is None: passwd = self.passwd 
        if host   is None: host = self.host
        if priv   is None: priv = 'all privileges'
        priv = clean_input(priv)

        cmd = "grant %s on %s.* to %s@%s identified by '%s'" 
        self.__execute(cmd % (priv,db,user,host,passwd) )

