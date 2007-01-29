drop database  if exists pvcache;

create database pvcache;
use pvcache;

drop table if exists cache;
drop table if exists info;
drop table if exists req;

create table cache (
  id     int(10) unsigned not null auto_increment,
  name   varchar(64) default null,
  type   varchar(64) default null,
  value  varchar(64) default null,
  cvalue varchar(64) default null,
  ts     double not null,
  primary key  (id));

create table req (
  id int(10) unsigned not null auto_increment,
  name varchar(64) default null,
  primary key  (id));

create table info (
  id int(10) unsigned not null auto_increment,
  ts double default null,
  datetime varchar(128) default null,
  pid int(10) unsigned default null,
  primary key  (id));

insert into info values (1,0.0,'created',0);
