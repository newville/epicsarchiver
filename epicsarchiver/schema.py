#!/usr/bin/env python
"""
text values for creating epicsarchiver databases

"""

pvdat_init_pv = """create table pv(
  id           int(10) unsigned not null auto_increment,
  name         varchar(64) not null,
  description  varchar(128) default null,
  data_table   varchar(16) default null,
  deadtime     double default '10',
  deadband     double default '0.00000001',
  graph_hi     tinyblob,
  graph_lo     tinyblob,
  graph_type   enum('normal','log','discrete') default null,
  type         enum('int','double','string','enum') not null,
  active       enum('yes','no') default 'yes',
  primary key (id),
  unique key name (name),
  key name_idx (name)
) default charset=latin1;
"""

pvdat_init_dat = """create table pvdat{idat:03d} (
  time double not null,
  pv_id int(10) unsigned not null,
  value varchar(4096),
  key pv_idx (pv_id)
) default charset=latin1;
"""

create_cachedb = """
create database {cache_db:s};
use {cache_db:s};

create table alerts (
  id        int(10) unsigned not null auto_increment,
  pvname    varchar(64) not null,
  name      varchar(256) not null,
  mailto    varchar(1024) default null,
  mailmsg   varchar(32768) default null,
  trippoint tinyblob,
  timeout   float default '30',
  compare   enum('eq','ne','le','lt','ge','gt') not null default 'eq',
  status    enum('alarm','ok') not null default 'ok',
  active    enum('yes','no') not null default 'yes',
  primary key (id)
  ) default charset=latin1;

create table cache (
  id        int(10) unsigned not null auto_increment,
  pvname    varchar(128) default null,
  type      varchar(64) not null default 'int',
  value     varchar(4096) default null,
  cvalue    varchar(4096) default null,
  ts        double default null,
  active    enum('yes','no') not null default 'yes',
  primary key (id),
  key pvname_id (pvname)
  ) default charset=latin1;

create table info (
  id        int(10) unsigned not null auto_increment,
  process   varchar(256) default null,
  status    enum('offline','running','stopping','unknown') not null default 'unknown',
  db        varchar(64) default null,
  datetime  varchar(64) default null,
  ts        double not null default '0',
  pid       int(10) unsigned not null default '0',
  primary key (id),
  unique key process (process(1))
  ) default charset=latin1;

insert into info values (1,'cache',   'offline','','',0, 0);
insert into info values (2,'archive', 'offline','','',0, 0);
insert into info values (3,'version', 'unknown','1','',0, 0);

create table pairs (
  id        int(10) unsigned not null auto_increment,
  pv1       varchar(128) default null,
  pv2       varchar(128) default null,
  score     int(10) unsigned not null default '1',
  primary key (id),
  key pair_idx (pv1,pv2)
  ) default charset=latin1;

create table pvextra (
  id        int(10) unsigned not null auto_increment,
  pv        varchar(128) default null,
  notes     varchar(512) default null,
  data      varchar(4096) default null,
  primary key(id)
  ) default charset=latin1;

create table requests (
  id        int(10) unsigned not null auto_increment,
  pvname    varchar(64) default null,
  ts        double default '0',
  action    enum('add','drop','suspend','ignore') not null default 'add',
  primary key (id)
  ) default charset=latin1;

create table runs (
  id        int(10) unsigned not null auto_increment,
  db        varchar(64) default null,
  notes     varchar(512) default null,
  start_time double not null default '0',
  stop_time  double not null default '0',
  primary key (id),
  unique key db (db)
  )  default charset=latin1;
"""

apache_config = """# apache wsgi configuration
# this should be added to your Apache configuration, as with
#   IncludeOptional {server_root:}/conf.d/pvarch.conf


WSGIScriptAlias /{web_url:s}  {web_dir:s}/pvarch.wsgi

<Directory {web_dir:s}>
   Options all
   Require all granted
   WSGIApplicationGroup %{{GLOBAL}}
</Directory>
"""


def initial_sql(config):
    """creates sql to initialize master cache database and
    first archive database
    """
    dbname = config.dat_format % (config.dat_prefix, 1)
    sql = [create_cachedb.format(cache_db=config.cache_db),
           "update info set db='{db:s}' where process='archive';".format(db=dbname),
           "create database {db:s}; use {db:s};".format(db=dbname),
           pvdat_init_pv]

    for idat in range(1, 129):
        sql.append(pvdat_init_dat.format(idat=idat))
    sql.append('; ')
    return '\n'.join(sql)
