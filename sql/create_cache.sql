DROP TABLE IF EXISTS cache;
CREATE TABLE cache (
  id     int(10) unsigned NOT NULL auto_increment,
  name   varchar(64) default NULL,
  type   varchar(64) default NULL,
  value  varchar(64) default NULL,
  cvalue varchar(64) default NULL,
  ts     double NOT NULL,
  PRIMARY KEY  (id)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;


DROP TABLE IF EXISTS info;
CREATE TABLE info (
  id int(10) unsigned NOT NULL auto_increment,
  ts double default NULL,
  datetime varchar(128) default NULL,
  pid int(10) unsigned default NULL,
  PRIMARY KEY  (id)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

LOCK TABLES info WRITE;
INSERT INTO info VALUES (1,0.0,'Created',0);
UNLOCK TABLES;

DROP TABLE IF EXISTS req;
CREATE TABLE req (
  id int(10) unsigned NOT NULL auto_increment,
  name varchar(64) default NULL,
  PRIMARY KEY  (id)
) ENGINE=InnoDB ;

