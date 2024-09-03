#!/usr/bin/env python
#
# setup script for EpicsArchiver.
# Use
#     python setup.py install

from setuptools import setup

setup(name        = 'epicsarchiver',
      version     = '2.2',
      author      = 'Matthew Newville',
      author_email= 'newville@cars.uchicago.edu',
      url         = 'https://github.com/newville/epicsarchiver/',
      license     = 'BSD',
      description = 'archiver for Epics PVs with web display',
      zip_safe    = False,
      package_dir = {'epicsarchiver': 'epicsarchiver'},
      packages    = ['epicsarchiver'],
      entry_points = {'console_scripts': ['pvarch = epicsarchiver:pvarch_main']},
      package_data = {'epicsarchiver.templates': ['templates/*'],
                      'epicsarchiver.static': ['static/*']},
      install_requires=['pyepics>=3.5.0',
                        'numpy>=1.14',
                        "tabulate",
                        "psutil",
                        "zarr",
                        'sqlalchemy>2.0',
                        'pymysql',
                        'toml',
                        'flask'])
