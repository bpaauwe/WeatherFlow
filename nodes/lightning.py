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

class LightningNode(polyinterface.Node):
    id = 'lightning'
    hint = [1,11,7,0]
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 25},  # Strikes
            {'driver': 'GV0', 'value': 0, 'uom': 83},  # Distance
            ]

    def SetUnits(self, u):
        self.units = u
        if (u == 'km'):
            self.drivers[0]['uom'] = 25
            self.drivers[1]['uom'] = 83
            self.id = 'lightning'
        elif (u == 'mi'): 
            self.drivers[0]['uom'] = 25
            self.drivers[1]['uom'] = 116
            self.id = 'lightningUK'

    def setDriver(self, driver, value):
        if (driver == 'GV0'):
            if (self.units != 'km'):
                value = round(value / 1.609344, 1)
        super(LightningNode, self).setDriver(driver, value, report=True, force=True)

    def update(self, ls, ld):
        self.setDriver('ST', ls)
        self.setDriver('GV0', ld)

