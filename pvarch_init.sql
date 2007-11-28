#
#
#  sql initialization for Epics PVArchiver master database
#

drop table if exists cache;
create table cache (
    id         int unsigned not null primary key auto_increment,
    pvname     varchar(64) not null,
    type       varchar(64) not null default 'int',
    value      tinyblob    default null,
    cvalue     varchar(64) default null,
    ts         double not null default 0,
    active     enum('yes','no') not null default 'yes');

drop table if exists runs;
create table runs (
    id         int unsigned not null primary key auto_increment,
    db         varchar(64)  default null unique key,
    notes      varchar(512) default null,
    start_time double not null default 0,
    stop_time  double not null default 0);

drop table if exists info;
create table info  (
    id         int unsigned not null primary key auto_increment,
    process    enum('archive','cache','monitor') not null default 'archive' unique key,
    status     enum('offline','running','stopping','unknown') not null default 'unknown',
    db         varchar(64) default null,
    datetime   varchar(64) default null,
    ts         double not null default 0,
    pid        int unsigned not null default 0);

insert into info values (1,'cache',   'offline','','',0.0, 0);
insert into info values (2,'archive', 'offline','','',0.0, 0);
insert into info values (3,'monitor', 'offline','','',0.0, 0);

drop table if exists requests;
create table requests (
    id         int unsigned not null primary key auto_increment,
    pvname     varchar(64) default null,
    ts         double default 0,
    action     enum('add','drop','suspend','ignore') not null default 'add');

drop table if exists alerts;
create table alerts (
    id         int unsigned not null primary key auto_increment,
    pvname     varchar(64) not null,
    name       varchar(256) not null, 
    mailto     varchar(256) default null,
    mailmsg    varchar(4096) default null,
    trippoint  tinyblob default null,
    timeout    float default 30,
    compare    enum('eq','ne','le','lt','ge','gt') not null default 'eq',
    status     enum('alarm','ok') not null default 'ok',
    active     enum('yes','no') not null default 'yes' );

drop table if exists pairs;
create table pairs (
    id         int unsigned not null primary key auto_increment,
    pv1        varchar(64) not null,
    pv2        varchar(64) not null,
    score      int unsigned not null default 1) ;

drop table if exists stations;
create table stations (
    id         int unsigned not null primary key auto_increment,
    name       varchar(64) not null unique key,
    notes      varchar(512) not null);

drop table if exists instruments;
create table instruments (
    id         int unsigned not null primary key auto_increment,
    name       varchar(64) not null,
    station    int unsigned not null,
    notes      varchar(512) not null);

drop table if exists instrument_pvs;
create table instrument_pvs (
    id         int unsigned not null primary key auto_increment,
    pvname     varchar(64) not null,
    inst       int unsigned not null);

drop table if exists instrument_positions;
create table instrument_positions (
    id         int unsigned not null primary key auto_increment,
    inst       int unsigned not null,
    name       varchar(128) not null,
    active     enum('yes','no') not null default 'yes',
    ts         double not null default 0);

