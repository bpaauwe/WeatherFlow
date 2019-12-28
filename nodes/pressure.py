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

class PressureNode(polyinterface.Node):
    id = 'pressure'
    hint = [1,11,3,0]
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 117},  # abs (station) press
            {'driver': 'GV0', 'value': 0, 'uom': 117}, # rel (sealevel) press
            {'driver': 'GV1', 'value': 0, 'uom': 25}  # trend
            ]
    mytrend = []


    def SetUnits(self, u):
        # can we dynmically set the drivers here also?
        # what about the ID, can we dynamically change that to change
        # the node def?
        self.units = u
        if (u == 'metric'):  # millibar
            self.drivers[0]['uom'] = 117
            self.drivers[1]['uom'] = 117
            self.id = 'pressure'
        elif (u == 'uk'):  # millibar
            self.drivers[0]['uom'] = 117 
            self.drivers[1]['uom'] = 117
            self.id = 'pressureUK'
        elif (u == 'us'):   # inHg
            self.drivers[0]['uom'] = 23
            self.drivers[1]['uom'] = 23
            self.id = 'pressureUS'

    # convert station pressure in millibars to sealevel pressure
    def toSeaLevel(self, station, elevation):
        i = 287.05  # gas constant for dry air
        a = 9.80665 # gravity
        r = 0.0065  # standard atmosphere lapse rate
        s = 1013.35 # pressure at sealevel
        n = 288.15  # sea level temperature

        l = a / (i * r)

        c = i * r / a

        u = math.pow(1 + math.pow(s / station, c) * (r * elevation / n), l)

        return (round((station * u), 3))

    # track pressures in a queue and calculate trend
    def updateTrend(self, current):
        t = 1  # Steady
        past = 0

        if len(self.mytrend) > 1:
            LOGGER.info('LAST entry = %f' % self.mytrend[-1])
        if len(self.mytrend) == 180:
            # This should be poping the last entry on the list (or the 
            # oldest item added to the list).
            past = self.mytrend.pop()

        if self.mytrend != []:
            # mytrend[0] seems to be the last entry inserted, not
            # the first.  So how do we get the last item from the
            # end of the array -- mytrend[-1]
            past = self.mytrend[-1]

        # calculate trend
        LOGGER.info('TREND %f to %f' % (past, current))
        if ((past - current) > 1):
            t = 0 # Falling
        elif ((past - current) < -1):
            t = 2 # Rising

        # inserts the value at index 0 and bumps all existing entries
        # up by one index
        self.mytrend.insert(0, current)

        return t

    # We want to override the SetDriver method so that we can properly
    # convert the units based on the user preference.
    def setDriver(self, driver, value):
        if (self.units == 'us' and driver != 'GV1' ):
            value = round(value * 0.02952998751, 3)
        super(PressureNode, self).setDriver(driver, value, report=True, force=True)

    def update(self, p, sl, trend):
        self.setDriver('ST', p)
        self.setDriver('GV0', sl)
        self.setDriver('GV1', trend)


