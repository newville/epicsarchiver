#
#
#  sql initialization for Epics PVArchiver master database
#

drop table if exists pvnames;
drop table if exists pairs;
drop table if exists instruments;
drop table if exists instrument_pvs;
drop table if exists instrument_positions;

drop table if exists runs;
drop table if exists cache;
drop table if exists info;
drop table if exists requests;
drop table if exists alerts;

create table pvnames (
    id         int unsigned not null primary key auto_increment,
    name       varchar(64) not null unique key,
    type       varchar(64) not null);

create table pairs (
    id         int unsigned not null primary key auto_increment,
    pv1        int unsigned not null,
    pv2        int unsigned not null,
    score      int unsigned not null default 1) ;

create table instruments (
    id         int unsigned not null primary key auto_increment,
    name       varchar(128) not null,
    station    varchar(128) not null,
    notes      varchar(512) not null);

create table instrument_pvs (
    id         int unsigned not null primary key auto_increment,
    pv         int unsigned not null,
    inst       int unsigned not null);

create table instrument_postions (
    id         int unsigned not null primary key auto_increment,
    inst       int unsigned not null,
    ts         double not null default 0,
    name       varchar(128) not null);

create table runs (
    id         int unsigned not null primary key auto_increment,
    db         varchar(32)  default null unique key,
    notes      varchar(512) default null,
    start_time double not null default 0,
    stop_time  double not null default 0);

create table cache (
    id         int unsigned not null primary key auto_increment,
    pv         int unsigned not null,
    value      tinyblob  default null,
    cvalue     varchar(64) default null,
    ts         double not null default 0,
    active     enum('yes','no') not null default 'yes');

create table requests (
    id         int unsigned not null primary key auto_increment,
    name       varchar(64) default null,
    action     enum('add','drop','suspend','ignore') not null default 'add');

create table alerts (
    id         int unsigned not null primary key auto_increment,
    pv         int unsigned not null,
    mailto     varchar(256) default null,
    mailmsg    varchar(1024) default null,
    trippoint  tinyblob default null,
    compare    enum('eq','ne','le','lt','ge','gt') not null default 'eq',
    status     enum('alarm','ok') not null default 'ok',
    active     enum('yes','no') not null default 'yes' );

create table info  (
    id         int unsigned not null primary key auto_increment,
    process    enum('archive','cache','monitor','unknown') not null default 'archive' unique key,
    status     enum('offline','running','stopping','unknown') not null default 'unknown',
    db         varchar(32) default null,
    datetime   varchar(64) default null,
    notes      varchar(256) default null,
    ts         double not null default 0,
    pid        int unsigned not null default 0);

insert into info values (1,'cache',   'offline','','','',0.0,0);
insert into info values (2,'archive', 'offline','','','',0.0,0);
insert into info values (3,'monitor', 'offline','','','',0.0,0);

