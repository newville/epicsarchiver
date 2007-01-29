drop database  if exists pvarchives;
create database pvarchives;
use pvarchives;

drop table if exists current;
drop table if exists pairs;
drop table if exists runs;

create table current (
  status enum('offline','running','stopping','unknown') default 'unknown',
  db varchar(32) default null,
  pid int(10) unsigned default null );


create table pairs (
  pv1 varchar(32) not null,
  pv2 varchar(32) not null,
  score int(10) unsigned default null);

create table runs (
  id smallint(5) unsigned not null auto_increment,
  db varchar(16) not null default '',
  notes varchar(255) default null,
  start_time int(11) not null default '0',
  stop_time int(11) not null default '0',
  primary key  (id),
  unique key db (db));

