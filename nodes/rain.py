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

class PrecipitationNode(polyinterface.Node):
    id = 'precipitation'
    hint = [1,11,5,0]
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 46},  # rate
            {'driver': 'GV0', 'value': 0, 'uom': 82}, # hourly
            {'driver': 'GV1', 'value': 0, 'uom': 82}, # daily
            {'driver': 'GV2', 'value': 0, 'uom': 82}, # weekly
            {'driver': 'GV3', 'value': 0, 'uom': 82}, # monthly
            {'driver': 'GV4', 'value': 0, 'uom': 82}, # yearly
            {'driver': 'GV5', 'value': 0, 'uom': 82}  # yesterday
            ]
    hourly_rain = 0
    daily_rain = 0
    weekly_rain = 0
    monthly_rain = 0
    yearly_rain = 0
    yesterday_rain = 0

    prev_hour = 0
    prev_day = 0
    prev_week = 0
    prev_month = 0
    prev_year = 0

    def InitializeRain(self, acc):
        self.daily_rain = acc['daily']
        self.hourly_rain = acc['hourly']
        self.weekly_rain = acc['weekly']
        self.monthly_rain = acc['monthly']
        self.yearly_rain = acc['yearly']
        self.yesterday_rain = acc['yesterday']

        self.prev_hour = acc['hour']
        self.prev_day = acc['day']
        self.prev_week = acc['week']
        self.prev_month = acc['month']
        self.prev_year = acc['year']

        now = datetime.datetime.now()

        # Need to compare saved date with current date and clear out 
        # any accumlations that are old.

        current_hour = now.hour
        if self.prev_hour != now.hour:
            LOGGER.info('Clearing old hourly data')
            self.prev_hour = now.hour
            self.hourly_rain = 0

        if self.prev_day != now.day:
            LOGGER.info('Clearing old daily, hourly data')
            self.yesterday_rain = self.daily_rain
            self.prev_day = now.day
            self.hourly_rain = 0
            self.daily_rain = 0

        if self.prev_week != now.isocalendar()[1]:
            LOGGER.info('Clearing old weekly, daily, hourly data')
            self.prev_week = now.isocalendar()[1]
            self.hourly_rain = 0
            self.daily_rain = 0
            self.weekly_rain = 0

        if self.prev_month != now.month:
            LOGGER.info('Clearing old monthly, daily, hourly data')
            self.prev_month = now.month
            self.hourly_rain = 0
            self.daily_rain = 0
            self.weekly_rain = 0
            self.monthly_rain = 0

        if self.prev_year != now.year:
            LOGGER.info('Clearing old yearly, monthly, daily, hourly data')
            self.prev_year = now.year
            self.hourly_rain = 0
            self.daily_rain = 0
            self.weekly_rain = 0
            self.monthly_rain = 0
            self.yearly_rain = 0


    def SetUnits(self, u):
        self.units = u
        if (u == 'mm'):
            self.drivers[0]['uom'] = 46
            self.drivers[1]['uom'] = 82
            self.drivers[2]['uom'] = 82
            self.drivers[3]['uom'] = 82
            self.drivers[4]['uom'] = 82
            self.drivers[5]['uom'] = 82
            self.drivers[6]['uom'] = 82
            self.id = 'precipitation'
        elif (u == 'in'): 
            self.drivers[0]['uom'] = 24
            self.drivers[1]['uom'] = 105
            self.drivers[2]['uom'] = 105
            self.drivers[3]['uom'] = 105
            self.drivers[4]['uom'] = 105
            self.drivers[5]['uom'] = 105
            self.drivers[6]['uom'] = 105
            self.id = 'precipitationUS'

    def hourly_accumulation(self, r):
        current_hour = datetime.datetime.now().hour
        if (current_hour != self.prev_hour):
            self.prev_hour = current_hour
            self.hourly_rain = 0

        self.hourly_rain += r
        return self.hourly_rain

    def daily_accumulation(self, r):
        current_day = datetime.datetime.now().day
        if (current_day != self.prev_day):
            self.yesterday_rain = self.daily_rain
            self.prev_day = current_day
            self.daily_rain = 0

        self.daily_rain += r
        return self.daily_rain

    def yesterday_accumulation(self):
        return self.yesterday_rain

    def weekly_accumulation(self, r):
        (y, w, d) = datetime.datetime.now().isocalendar()
        if w != self.prev_week:
            self.prev_week = w
            self.weekly_rain = 0

        self.weekly_rain += r
        return self.weekly_rain

    def monthly_accumulation(self, r):
        current_month = datetime.datetime.now().month
        if (current_month != self.prev_month):
            self.prev_month = current_month
            self.monthly_rain = 0

        self.monthly_rain += r
        return self.monthly_rain

    def yearly_accumulation(self, r):
        current_year = datetime.datetime.now().year
        if (current_year != self.prev_year):
            self.prev_year = current_year
            self.yearly_rain = 0

        self.yearly_rain += r
        return self.yearly_rain

        
    def setDriver(self, driver, value):
        if (self.units == 'in'):
            value = round(value * 0.03937, 2)
        super(PrecipitationNode, self).setDriver(driver, value, report=True, force=True)

