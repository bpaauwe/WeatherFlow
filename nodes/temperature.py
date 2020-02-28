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

class TemperatureNode(polyinterface.Node):
    id = 'temperature'
    hint = [1,11,1,0]
    units = 'us'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 17},
            {'driver': 'GV0', 'value': 0, 'uom': 17}, # feels like
            {'driver': 'GV1', 'value': 0, 'uom': 17}, # dewpoint
            {'driver': 'GV2', 'value': 0, 'uom': 17}, # heat index
            {'driver': 'GV3', 'value': 0, 'uom': 17}  # windchill
            ]

    def SetUnits(self, u):
        self.units = u
        if (u == 'c'):  # C
            self.drivers[0]['uom'] = 4
            self.drivers[1]['uom'] = 4
            self.drivers[2]['uom'] = 4
            self.drivers[3]['uom'] = 4
            self.drivers[4]['uom'] = 4
            self.id = 'temperature'
        elif (u == 'uk'):  # C
            self.drivers[0]['uom'] = 4 
            self.drivers[1]['uom'] = 4
            self.drivers[2]['uom'] = 4
            self.drivers[3]['uom'] = 4
            self.drivers[4]['uom'] = 4
            self.id = 'temperatureUK'
        elif (u == 'f'):   # F
            self.drivers[0]['uom'] = 17
            self.drivers[1]['uom'] = 17
            self.drivers[2]['uom'] = 17
            self.drivers[3]['uom'] = 17
            self.drivers[4]['uom'] = 17
            self.id = 'temperatureUS'

    def Dewpoint(self, t, h):
        b = (17.625 * t) / (243.04 + t)
        rh = h / 100.0

        if rh <= 0:
            return 0

        c = math.log(rh)
        dewpt = (243.04 * (c + b)) / (17.625 - c - b)
        return round(dewpt, 1)

    def ApparentTemp(self, t, ws, h):
        wv = h / 100.0 * 6.105 * math.exp(17.27 * t / (237.7 + t))
        at =  t + (0.33 * wv) - (0.70 * ws) - 4.0
        return round(at, 1)

    def Windchill(self, t, ws):
        # really need temp in F and speed in MPH
        tf = (t * 1.8) + 32
        #mph = ws / 0.44704 # from m/s to mph
        mph = ws / 1.609  # from kph to mph

        wc = 35.74 + (0.6215 * tf) - (35.75 * math.pow(mph, 0.16)) + (0.4275 * tf * math.pow(mph, 0.16))

        if (tf <= 50.0) and (mph >= 5.0):
            return round((wc - 32) / 1.8, 1)
        else:
            return t

    def Heatindex(self, t, h):
        tf = (t * 1.8) + 32
        c1 = -42.379
        c2 = 2.04901523
        c3 = 10.1433127
        c4 = -0.22475541
        c5 = -6.83783 * math.pow(10, -3)
        c6 = -5.481717 * math.pow(10, -2)
        c7 = 1.22874 * math.pow(10, -3)
        c8 = 8.5282 * math.pow(10, -4)
        c9 = -1.99 * math.pow(10, -6)

        hi = (c1 + (c2 * tf) + (c3 * h) + (c4 * tf * h) + (c5 * tf *tf) + (c6 * h * h) + (c7 * tf * tf * h) + (c8 * tf * h * h) + (c9 * tf * tf * h * h))

        if (tf < 80.0) or (h < 40.0):
            return t
        else:
            return round((hi - 32) / 1.8, 1)

    def setDriver(self, driver, value):
        if (self.units == "f"):
            value = (value * 1.8) + 32  # convert to F

        super(TemperatureNode, self).setDriver(driver, round(value, 1), report=True, force=True)

    # Possible TODO: do calculations here. I.E. pass in temp, ws, humidity
    def update(self, t, fl, dp, hi, wc):
        self.setDriver('ST', t)
        self.setDriver('GV0', fl)
        self.setDriver('GV1', dp)
        self.setDriver('GV2', hi)
        self.setDriver('GV3', wc)


