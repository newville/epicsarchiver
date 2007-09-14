#!/usr/bin/env python
#
import MySQLdb
import sys
import os
import array

from time import sleep

from util import string_literal, clean_string
from config import dbuser, dbpass, dbhost, mysqldump

def db_connect(dbname='test',user=dbuser,passwd=dbpass,
               host=dbhost,autocommit=1):
    return SimpleDB(db=dbname,user=user, passwd=passwd,
                    host=host, autocommit=autocommit)

def save_db(dbname=None,compress=True):
    if dbname is not None:
        db = db_connect(dbname=dbname)
        db.use(dbname)
        db.safe_dump(compress=compress)
        
class SimpleTable:
    """ simple class for a MySQL table ...
    a table must have entry ID"""
    def __init__(self,db, table=None):
        self.db = db
        if db == None:
            print "Warning SimpleTable needs a database"
            return None

        self.fields  = []
        self.primary = None
        self._name = None
        if table in self.db.table_list:
            self._name = table
        else:
            table = table.upper()
            if (table in self.db.table_list):
                self._name = table
            else:
                self.db.write("Table %s not available in %s " % (table,db))
                return None

        self.db.execute("describe %s" % self._name)
        # print "done: describe %s" % self._name
        for j in self.db.fetchall():
            if (j['key'] == 'PRI'):  self.primary = j['field']
            self.fields.append(j['field'].upper())
            
    def check_args(self,**args):
        """ check that the keys of the passed args are all available as table columns
           returns 0 on failure, 1 on success   """
        return self.check_columns(args.keys())

    def check_columns(self,l):
        """ check that the list of args are all available as table columns
        returns 0 on failure, 1 on success
        """
        for i in l:
            if i.upper() not in self.fields: return False
        return True
    
    def select_all(self):
        return self.select_where()
    
    def select_where(self,**args):
        """check for a table row, and return matches"""
        if (self.check_args(**args)):
            q = "select * from %s where 1=1" % (self._name)
            for k,v in args.items():
                k = clean_string(k)
                v = string_literal(v)
                q = "%s and %s=%s" % (q,k,v)
            self.db.execute(q)
            return self.db.fetchall()
        return 0

    def select(self,vals='*', where='1=1'):
        """check for a table row, and return matches"""
        
        q = "select %s from %s where %s" % (vals, self._name, where)
        self.db.execute(q)
        return self.db.fetchall()

    def update(self,where=None,set=None):
        """update a table row with set and where dictionaries:

           table.update_where({'x':1},{'y':'a'})
        translates to
           update TABLE set x=1 where y=a
           """
        if where==None or set==None:
            self.db.write("update must give where and set arguments (dictionaries)")
            return
        try:
            q = ''
            if self.check_columns(set.keys()+where.keys()):
                q = "update %s set" % (self._name)
                for k,v in set.items():
                    k = clean_string(k)
                    v = string_literal(v)
                    q = "%s %s=%s," % (q,k,v)
                q = "%s where " % (q[:-1])  # strip off last ','

                for k,v in where.items():
                    k = clean_string(k)
                    v = string_literal(v)
                    q = "%s %s=%s and" % (q,k,v)
                q = q[:-3]  # strip off last 'and'
            self.db.execute(q)
        except:
            self.db.write('update failed ')
        return self.db.affected_rows()

    def insert(self,**args):
        "add a new table row "
        ok = self.check_args(**args)
        if (ok == 0):
            self.db.write("Bad argument for insert ")
            return 0
        q  = "INSERT INTO %s SET " % (self._name)
        for k,v in args.items():
            field = clean_string(k.upper())
            if (v == None): v = ''
            q = "%s %s=%s," % (q,field,self.db.string_literal(v))
        cmd = q[:-1]  # strip of trailing ','
        self.db.execute(cmd)
        return self.db.affected_rows()

    def __repr__(self):
        """ shown when printing instance:
        >>>p = Table()
        >>>print p
        """
        return "<MyTable name=%s>" % ( self._name )

class SimpleDB:
    message_types= {'normal': '',
                    'warning': 'Warning: ',
                    'error': 'Error: ',
                    'fatal': 'Fatal Error: '}

    SimpleDB_Exception = 'Simple DB Exception'
    def __init__(self,db=None, user=None, passwd=None, host=None,
                 debug=0, messenger=None,bindir=None,autocommit=1):

        self.debug     = debug
        self.messenger = messenger or sys.stdout
        self.user      = user      or 'epics'
        self.passwd    = passwd    or 'epics'
        self.dbname    = db        or 'test'
        self.host      = host      or 'localhost'

        self.tables = []
        # start mysql connection
        try:
            self.db   = MySQLdb.connect(user=self.user, db=self.dbname,
                                        passwd=self.passwd,
                                        host=self.host )
        except:
            self.write("Could not start MySQL on %s for database %s" %
                       (self.host, self.dbname),   status='fatal')

        self.cursor = self.db.cursor(cursorclass=MySQLdb.cursors.DictCursor)
        self.use(self.dbname)
        self.execute("set AUTOCOMMIT=%i" % autocommit)

    def close(self):
        " close db connection"
        self.cursor = 0
        self.db.close()
        
    def safe_dump(self, file=None,compress=False):
        if (file==None): file = "%s.sql" % self.dbname
        cmd = "%s %s > %s" % (mysqldump, self.dbname, file)
        try:
            os.system("%s" % (cmd))
        except:
            self.write("could not dump database %s to file %s" % (self.dbname,file))
        if compress:
            try:
                os.system("gzip %s" % (file))
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
            for x in lines:
                if not x.startswith('#'):
                    self.execute(x[:-1])
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
        self.table_list = []
        self.tables     = {}

        if self.execute("use %s" % db) != None:
            self.dbname  = db
            n = self.execute("show TABLES")
            x = self.fetchall()
            if (n>0): self.table_list = [i.values()[0] for i in self.fetchall()]
            for i in self.table_list:
                self.tables[i] = SimpleTable(self,table=i)

    def execute(self,q):
        "execute query"
        try:
            if (self.debug == 1): print "SQL> %s" % (q)
            return self.cursor.execute(q)
        except:
            sleep(0.02)
            try:
                if (self.debug == 1): print "SQL> %s" % (q)
                return self.cursor.execute(q)
            except:
                self.write("SQL Query Failed: %s " % (q))
        return None
            
    def fetchone(self):
        "return next row from most recent query"
        #return self.cursor.fetchone()
        return self._normalize_dict(self.cursor.fetchone())
 
    def affected_rows(self):
        try:
            return self.cursor.rowcount()
        except:
            return self.db.affected_rows()

    def _normalize_dict(self, dict):
        t =  {}
        if self.debug==1: print '_normalize dict: ', dict
        if (dict == None): return t
        for k,v in dict.items():
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
        r = []
        for i  in self.cursor.fetchall():
            r.append(self._normalize_dict(i))
        return tuple(r)

    def exec_fetch(self,q):
        self.execute(q)
        return self.fetchall()
