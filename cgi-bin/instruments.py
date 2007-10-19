#!/usr/bin/python
from mod_python import apache
from EpicsArchiver import WebInstruments

def index(req,station=None,instrument=None,pv=None,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebInstruments(arch=arch)
    arch = p.arch

    return p.show(station=station,instrument=instrument,pv=pv,**kw)


def add_instrument(req,station='',**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebInstruments(arch=arch)
    arch = p.arch

    return p.add_instrument(station=station,**kw)


def modify_instrument(req,station='',**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebInstruments(arch=arch)
    arch = p.arch

    return p.modify_instrument(station=station,**kw)


def add_station(req,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None

    p = WebInstruments(arch=arch)
    arch = p.arch

    return p.add_station(**kw)

def view_position(req,**kw):
    global arch
    try:
        arch is None
    except NameError:
        arch = None
    p = WebInstruments(arch=arch)
    arch = p.arch

    return p.view_position(**kw)

