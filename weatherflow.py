#!/usr/bin/env python3
"""
Polyglot v2 node server for WeatherFlow Weather Station data.
Copyright (c) 2018 Robert Paauwe
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

class Controller(polyinterface.Controller):
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.name = 'WeatherFlow'
        self.address = 'hub'
        self.primary = self.address
        self.hb = 0
        self.hub_timestamp = 0
        self.poly.onConfig(self.process_config)

    def process_config(self, config):
        # this seems to get called twice for every change, why?
        # What does config represent?
        LOGGER.info("process_config: Enter");

        if 'Units' in self.polyConfig['customParams']:
            self.units = self.polyConfig['customParams']['Units'].lower()
            for node in self.nodes:
                if (node != 'hub' and node != 'controller'):
                    LOGGER.info("Setting node " + node + " to units " + self.units);
                    self.nodes[node].SetUnits(self.units)
                    self.addNode(self.nodes[node])
                else:
                    LOGGER.info("Skipping node " + node)
            LOGGER.info("Finished unit configuration.")

        if 'Elevation' in self.polyConfig['customParams']:
            self.elevation = self.polyConfig['customParams']['Elevation']

        LOGGER.info("Finished with configuration.")

        #typed_params = config.get('typedCustomData')
        #for param in typed_params:
        #    LOGGER.info("param = " + typed_params[param]);

    def start(self):
        LOGGER.info('Starting WeatherFlow Node Server')
        self.check_params()
        self.discover()

        # TODO: Is this where we need to set all the node id's and
        #       update the nodes to use the right nodedefs?
        LOGGER.info("Start updating nodes with unit information")
        for node in self.nodes:
            if (node != 'controller'):
                LOGGER.info("Setting node " + node + " to units " + self.units);
                self.nodes[node].SetUnits(self.units)

        LOGGER.info("Finished updating nodes with unit information")

        LOGGER.info('starting thread for UDP data')
        threading.Thread(target = self.udp_data).start()
        #for node in self.nodes:
        #       LOGGER.info (self.nodes[node].name + ' is at index ' + node)
        LOGGER.info('WeatherFlow Node Server Started.')

    def shortPoll(self):
        pass

    def longPoll(self):
        """
                This is where we'd want to poll the WF servers if
                we wanted to use that method to get data. But currently
                we get data via the local UDP broadcasts.
        """
        self.heartbeat()
        self.set_hub_timestamp()

    def query(self):
        for node in self.nodes:
            self.nodes[node].reportDrivers()
        self.set_hub_timestamp()

    def discover(self, *args, **kwargs):
        """
        Add basic weather sensor nodes
                - Temperature (temp, dewpoint, heat index, wind chill, feels)
                - Humidity
                - Pressure (abs, sealevel, trend)
                - Wind (speed, gust, direction, gust direction, etc.)
                - Precipitation (rate, hourly, daily, weekly, monthly, yearly)
                - Light (UV, solar radiation, lux)
                - Lightning (strikes, distance)
        """
        self.addNode(TemperatureNode(self, self.address, 'temperature', 'Temperatures'))
        self.addNode(HumidityNode(self, self.address, 'humidity', 'Humidity'))
        self.addNode(PressureNode(self, self.address, 'pressure', 'Barometric Pressure'))
        self.addNode(WindNode(self, self.address, 'wind', 'Wind'))
        self.addNode(PrecipitationNode(self, self.address, 'rain', 'Precipitation'))
        self.addNode(LightNode(self, self.address, 'light', 'Illumination'))
        self.addNode(LightningNode(self, self.address, 'lightning', 'Lightning'))

    def heartbeat(self):
        LOGGER.debug('heartbeat hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def set_hub_timestamp(self):
        s = int(time.time() - self.hub_timestamp)
        LOGGER.debug("set_hub_timestamp: {}".format(s))
        self.setDriver('GV4', s)

    def delete(self):
        self.stopping = True
        LOGGER.info('Removing WeatherFlow node server.')

    def stop(self):
        self.stopping = True
        LOGGER.debug('Stopping WeatherFlow node server.')

    def check_params(self):
        """
        Elevation, UDP port, and Units for now.
        """
        default_port = 50222
        default_elevation = 0
        default_units = "metric"
        if 'ListenPort' in self.polyConfig['customParams']:
            self.udp_port = int(self.polyConfig['customParams']['ListenPort'])
        else:
            self.udp_port = default_port

        if 'Units' in self.polyConfig['customParams']:
            self.units = self.polyConfig['customParams']['Units'].lower()
        else:
            self.units = default_units

        if 'Elevation' in self.polyConfig['customParams']:
            self.elevation = self.polyConfig['customParams']['Elevation']
        else:
            self.elevation = default_elevation

        # Make sure they are in the params
        self.addCustomParam({'ListenPort': self.udp_port,
                    'Units': self.units,
                    'Elevation': self.elevation})

        # Remove all existing notices
        self.removeNoticesAll()

        # Add a notice?

    def remove_notices_all(self,command):
        LOGGER.info('remove_notices_all:')
        # Remove all existing notices
        self.removeNoticesAll()

    def update_profile(self,command):
        LOGGER.info('update_profile:')
        st = self.poly.installprofile()
        return st

    def udp_data(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', self.udp_port))
        windspeed = 0

        LOGGER.info("Starting UDP receive loop")
        while self.stopping == False:
            hub = s.recvfrom(1024)
            data = json.loads(hub[0].decode("utf-8")) # hub is a truple (json, ip, port)

            """
            Depending on the type of data recieved, process it and
            update the correct node.
                                indexes are lower case names. I.E.
                                self.nodes['temperature']
            """
            if (data["type"] == "obs_air"):
                # process air data
                t = data['obs'][0][0] # ts
                p = data['obs'][0][1] # pressure
                t = data['obs'][0][2] # temp
                h = data['obs'][0][3] # humidity
                ls = data['obs'][0][4] # strikes
                ld = data['obs'][0][5] # distance

                sl = self.nodes['pressure'].toSeaLevel(p, 400)
                self.nodes['pressure'].setDriver('ST', sl)
                self.nodes['pressure'].setDriver('GV0', p)
                trend = self.nodes['pressure'].updateTrend(p)
                self.nodes['pressure'].setDriver('GV1', trend)

                self.nodes['temperature'].setDriver('ST', t)
                fl = self.nodes['temperature'].ApparentTemp(t, windspeed, h)
                self.nodes['temperature'].setDriver('GV0', fl)
                dp = self.nodes['temperature'].Dewpoint(t, h)
                self.nodes['temperature'].setDriver('GV1', dp)
                hi = self.nodes['temperature'].Heatindex(t, h)
                self.nodes['temperature'].setDriver('GV2', hi)
                wc = self.nodes['temperature'].Windchill(t, windspeed)
                self.nodes['temperature'].setDriver('GV3', wc)

                self.nodes['humidity'].setDriver('ST', h)

                self.nodes['lightning'].setDriver('ST', ls)
                self.nodes['lightning'].setDriver('GV0', ld)

                self.setDriver('GV0', data['obs'][0][6], report=True, force=True)


            if (data["type"] == "obs_sky"):
                # process sky data
                il = data['obs'][0][1]  # Illumination
                uv = data['obs'][0][2]  # UV Index
                rr = data['obs'][0][3]  # rain
                wl = data['obs'][0][4] * (18 / 5) # wind lull
                ws = data['obs'][0][5] * (18 / 5) # wind speed
                wg = data['obs'][0][6] * (18 / 5) # wind gust
                wd = data['obs'][0][7]  # wind direction
                it = data['obs'][0][9]  # reporting interval
                sr = data['obs'][0][10]  # solar radiation

                windspeed = ws

                self.nodes['wind'].setDriver('ST', ws)
                self.nodes['wind'].setDriver('GV0', wd)
                self.nodes['wind'].setDriver('GV1', wg)
                self.nodes['wind'].setDriver('GV2', wd)
                self.nodes['wind'].setDriver('GV3', wl)

                self.nodes['light'].setDriver('ST', uv)
                self.nodes['light'].setDriver('GV0', sr)
                self.nodes['light'].setDriver('GV1', il)

                rr = (rr * 60) / it
                self.nodes['rain'].setDriver('ST', rr)

                rh = self.nodes['rain'].hourly_accumulation(rr)
                self.nodes['rain'].setDriver('GV1', rh)
                rd = self.nodes['rain'].daily_accumulation(rr)
                self.nodes['rain'].setDriver('GV2', rd)
                #self.nodes['rain'].setDriver('GV3', 10.2)

                self.setDriver('GV1', data['obs'][0][8], report=True, force=True)

            if (data["type"] == "device_status"):
                if "AR" in data["serial_number"]:
                    self.setDriver('GV2', data['rssi'], report=True, force=True)
                if "SK" in data["serial_number"]:
                    self.setDriver('GV3', data['rssi'], report=True, force=True)

            if (data["type"] == "hub_status"):
                # This comes every 10 seconds, but we only update the driver
                # during longPoll, so just save it.
                #LOGGER.debug("hub_status: time={} {}".format(time.time(),data))
                if "timestamp" in data:
                    self.hub_timestamp = data['timestamp']

    def SetUnits(self, u):
        self.units = u


    id = 'WeatherFlow'
    name = 'WeatherFlow'
    address = 'hub'
    stopping = False
    hint = 0xffffff
    units = 'metric'
    commands = {
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile,
        'REMOVE_NOTICES_ALL': remove_notices_all
    }
    # Hub status information here: battery and rssi values.
    drivers = [
            {'driver': 'ST', 'value': 1, 'uom': 2},
            {'driver': 'GV0', 'value': 0, 'uom': 72},  # Air battery level
            {'driver': 'GV1', 'value': 0, 'uom': 72},  # Sky battery level
            {'driver': 'GV2', 'value': 0, 'uom': 25},  # Air RSSI
            {'driver': 'GV3', 'value': 0, 'uom': 25},  # Sky RSSI
            {'driver': 'GV4', 'value': 0, 'uom': 57}   # Hub seconds since seen
            ]


class TemperatureNode(polyinterface.Node):
    id = 'temperature'
    hint = 0xffffff
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
        if (u == 'metric'):  # C
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
        elif (u == 'us'):   # F
            self.drivers[0]['uom'] = 17
            self.drivers[1]['uom'] = 17
            self.drivers[2]['uom'] = 17
            self.drivers[3]['uom'] = 17
            self.drivers[4]['uom'] = 17
            self.id = 'temperatureUS'

    def Dewpoint(self, t, h):
        b = (17.625 * t) / (243.04 + t)
        rh = h / 100.0
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
        mph = ws / 0.44704

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
        if (self.units == "us"):
            value = (value * 1.8) + 32  # convert to F

        super(TemperatureNode, self).setDriver(driver, round(value, 1), report=True, force=True)



class HumidityNode(polyinterface.Node):
    id = 'humidity'
    hint = 0xffffff
    units = 'metric'
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 22}]

    def SetUnits(self, u):
        self.units = u

    def setDriver(self, driver, value):
        super(HumidityNode, self).setDriver(driver, value, report=True, force=True)

class PressureNode(polyinterface.Node):
    id = 'pressure'
    hint = 0xffffff
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 117},  # abs press
            {'driver': 'GV0', 'value': 0, 'uom': 117}, # rel press
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
        i = 287.05
        a = 9.80665
        r = 0.0065
        s = 1013.35 # pressure at sealevel
        n = 288.15

        l = a / (i * r)
        c = i * r / a
        u = math.pow(1 + math.pow(s / station, c) * (r * elevation / n), 1)

        return (round((station * u), 3))

    # track pressures in a queue and calculate trend
    def updateTrend(self, current):
        t = 0
        past = 0

        if len(self.mytrend) == 180:
            past = self.mytrend.pop()

        if self.mytrend != []:
            past = self.mytrend[0]

        # calculate trend
        if ((past - current) > 1):
            t = -1
        elif ((past - current) < -1):
            t = 1

        self.mytrend.insert(0, current)
        return t

    # We want to override the SetDriver method so that we can properly
    # convert the units based on the user preference.
    def setDriver(self, driver, value):
        if (self.units == 'us'):
            value = round(value * 0.02952998751, 3)
        super(PressureNode, self).setDriver(driver, value, report=True, force=True)


class WindNode(polyinterface.Node):
    id = 'wind'
    hint = 0xffffff
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

class PrecipitationNode(polyinterface.Node):
    id = 'precipitation'
    hint = 0xffffff
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 46},  # rate
            {'driver': 'GV0', 'value': 0, 'uom': 82}, # hourly
            {'driver': 'GV1', 'value': 0, 'uom': 82}, # daily
            {'driver': 'GV2', 'value': 0, 'uom': 82}, # weekly
            {'driver': 'GV3', 'value': 0, 'uom': 82}, # monthly
            {'driver': 'GV4', 'value': 0, 'uom': 82}  # yearly
            ]
    hourly_rain = 0
    daily_rain = 0
    weekly_rain = 0
    monthly_rain = 0
    yearly_rain = 0

    prev_hour = 0
    prev_day = 0
    prev_week = 0

    def SetUnits(self, u):
        self.units = u
        if (u == 'metric'):
            self.drivers[0]['uom'] = 46
            self.drivers[1]['uom'] = 82
            self.drivers[2]['uom'] = 82
            self.drivers[3]['uom'] = 82
            self.drivers[4]['uom'] = 82
            self.drivers[5]['uom'] = 82
            self.id = 'precipitation'
        elif (u == 'uk'):
            self.drivers[0]['uom'] = 46
            self.drivers[1]['uom'] = 82
            self.drivers[2]['uom'] = 82
            self.drivers[3]['uom'] = 82
            self.drivers[4]['uom'] = 82
            self.drivers[5]['uom'] = 82
            self.id = 'precipitationUK'
        elif (u == 'us'):
            self.drivers[0]['uom'] = 24
            self.drivers[1]['uom'] = 105
            self.drivers[2]['uom'] = 105
            self.drivers[3]['uom'] = 105
            self.drivers[4]['uom'] = 105
            self.drivers[5]['uom'] = 105
            self.id = 'precipitationUS'

    def hourly_accumulation(self, r):
        current_hour = datetime.datetime.now().hour
        if (current_hour != self.prev_hour):
            self.prev_hour = current_hour
            self.hourly = 0

        self.hourly_rain += r
        return self.hourly_rain

    def daily_accumulation(self, r):
        current_day = datetime.datetime.now().day
        if (current_day != self.prev_day):
            self.prev_day = current_day
            self.daily_rain = 0

        self.daily_rain += r
        return self.daily_rain

    def weekly_accumulation(self, r):
        current_week = datetime.datetime.now().day
        if (current_weekday != self.prev_weekday):
            self.prev_week = current_weekday
            self.weekly_rain = 0

        self.weekly_rain += r
        return self.weekly_rain


    def setDriver(self, driver, value):
        if (self.units == 'us'):
            value = round(value * 0.03937, 2)
        super(PrecipitationNode, self).setDriver(driver, value, report=True, force=True)

class LightNode(polyinterface.Node):
    id = 'light'
    units = 'metric'
    hint = 0xffffff
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 71},  # UV
            {'driver': 'GV0', 'value': 0, 'uom': 74},  # solar radiation
            {'driver': 'GV1', 'value': 0, 'uom': 36},  # Lux
            ]

    def SetUnits(self, u):
        self.units = u

    def setDriver(self, driver, value):
        super(LightNode, self).setDriver(driver, value, report=True, force=True)

class LightningNode(polyinterface.Node):
    id = 'lightning'
    hint = 0xffffff
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 25},  # Strikes
            {'driver': 'GV0', 'value': 0, 'uom': 83},  # Distance
            ]

    def SetUnits(self, u):
        self.units = u
        if (u == 'metric'):
            self.drivers[0]['uom'] = 25
            self.drivers[1]['uom'] = 83
            self.id = 'lightning'
        elif (u == 'uk'):
            self.drivers[0]['uom'] = 25
            self.drivers[1]['uom'] = 116
            self.id = 'lightningUK'
        elif (u == 'us'):
            self.drivers[0]['uom'] = 25
            self.drivers[1]['uom'] = 116
            self.id = 'lightningUS'

    def setDriver(self, driver, value):
        if (driver == 'GV0'):
            if (self.units != 'metric'):
                value = round(value / 1.609344, 1)
        super(LightningNode, self).setDriver(driver, value, report=True, force=True)


if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('WeatherFlow')
        """
        Instantiates the Interface to Polyglot.
        """
        polyglot.start()
        """
        Starts MQTT and connects to Polyglot.
        """
        control = Controller(polyglot)
        """
        Creates the Controller Node and passes in the Interface
        """
        control.runForever()
        """
        Sits around and does nothing forever, keeping your program running.
        """
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
