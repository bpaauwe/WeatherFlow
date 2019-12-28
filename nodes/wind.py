#!/usr/bin/env python3
"""
Polyglot v2 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019 Robert Paauwe
"""
import polyinterface
import sys
import time
import datetime
import urllib3
import json
import socket
import math
import threading

LOGGER = polyinterface.LOGGER

class WindNode(polyinterface.Node):
    id = 'wind'
    hint = [1,11,4,0]
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 32},  # speed
            {'driver': 'GV0', 'value': 0, 'uom': 76}, # direction
            {'driver': 'GV1', 'value': 0, 'uom': 32}, # gust
            {'driver': 'GV2', 'value': 0, 'uom': 76}, # gust direction
            {'driver': 'GV3', 'value': 0, 'uom': 32} # lull
            ]

    def SetUnits(self, u):
        self.units = u
        if (u == 'metric'):
            self.drivers[0]['uom'] = 32
            self.drivers[2]['uom'] = 32
            self.drivers[4]['uom'] = 32
            self.id = 'wind'
        elif (u == 'uk'): 
            self.drivers[0]['uom'] = 48
            self.drivers[2]['uom'] = 48
            self.drivers[4]['uom'] = 48
            self.id = 'windUK'
        elif (u == 'us'): 
            self.drivers[0]['uom'] = 48
            self.drivers[2]['uom'] = 48
            self.drivers[4]['uom'] = 48
            self.id = 'windUS'

    def setDriver(self, driver, value):
        if (driver == 'ST' or driver == 'GV1' or driver == 'GV3'):
            if (self.units != 'metric'):
                value = round(value / 1.609344, 2)
        super(WindNode, self).setDriver(driver, value, report=True, force=True)

    def update(self, ws, wd, wg, wl):
        self.setDriver('ST', ws)
        self.setDriver('GV0', wd)
        self.setDriver('GV1', wg)
        self.setDriver('GV2', wd)
        self.setDriver('GV3', wl)

