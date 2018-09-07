#!/usr/bin/env python3
"""
Polyglot v2 node server for WeatherFlow Weather Station data.
Copyright (c) 2018 Robert Paauwe
"""
import polyinterface
import sys
import time
import httplib
import json
import socket
import math
import threading
import Queue

LOGGER = polyinterface.LOGGER
"""
polyinterface has a LOGGER that is created by default and logs to:
logs/debug.log
You can use LOGGER.info, LOGGER.warning, LOGGER.debug, LOGGER.error levels as needed.
"""

class Controller(polyinterface.Controller):
    """
    The Controller Class is the primary node from an ISY perspective.
    It is a Superclass of polyinterface.Node so all methods from
    polyinterface.Node are available to this class as well.

    Class Variables:
    self.nodes:     Dictionary of nodes. Includes the Controller node.
                  Keys are the node addresses
    self.name:      String name of the node
    self.address: String Address of Node, must be less than 14 characters
                  (ISY limitation)
    self.polyConfig: Full JSON config dictionary received from Polyglot for
                     the controller Node
    self.added:     Boolean Confirmed added to ISY as primary node
    self.config:  Dictionary, this node's Config

    Class Methods (not including the Node methods):
    start():
        Once the NodeServer config is received from Polyglot this method
        is automatically called.
    addNode(polyinterface.Node, update = False):
        Adds Node to self.nodes and polyglot/ISY. This is called
        for you on the controller itself. Update = True overwrites the
        existing Node data.
    updateNode(polyinterface.Node):
        Overwrites the existing node data here and on Polyglot.
    delNode(address):
        Deletes a Node from the self.nodes/polyglot and ISY. Address is the
        Node's Address
    longPoll():
        Runs every longPoll seconds (set initially in the server.json or
        default 10 seconds)
    shortPoll():
        Runs every shortPoll seconds (set initially in the server.json or
        default 30 seconds)
    query():
        Queries and reports ALL drivers for ALL nodes to the ISY.
    getDriver('ST'):
        gets the current value from Polyglot for driver 'ST' returns a
        STRING, cast as needed
    runForever():
        Easy way to run forever without maxing your CPU or doing some silly
        'time.sleep' nonsense. this joins the underlying queue query thread
        and just waits for it to terminate which never happens.
    """
    def __init__(self, polyglot):
        """
        Optional.
        Super runs all the parent class necessities. You do NOT have
        to override the __init__ method, but if you do, you MUST call super.
        """
        super(Controller, self).__init__(polyglot)

    def start(self):
        """
        Optional.
        Polyglot v2 Interface startup done. Here is where you start your
        integration.  This will run, once the NodeServer connects to
        Polyglot and gets it's config.
        In this example I am calling a discovery method. While this is optional,
        this is where you should start. No need to Super this method, the parent
        version does nothing.
        """
        LOGGER.info('Starting WeatherFlow Node Server')
        self.check_params()
        self.discover()

        """
        TODO: Is this where we start the UDP monitor thread?
        What is the index for the node array?
        """
        LOGGER.info('starting thread for UDP data')
        threading.Thread(target = self.udp_data).start()
        #for node in self.nodes:
        #       LOGGER.info (self.nodes[node].name + ' is at index ' + node)
        LOGGER.info('WeatherFlow Node Server Started.')

    def shortPoll(self):
        """
        Optional.
        This runs every 10 seconds. You would probably update your nodes
        either here or longPoll. No need to Super this method the parent
        version does nothing.
        The timer can be overriden in the server.json.
        """
        pass

    def longPoll(self):
        """
                This is where we'd want to poll the WF servers if
                we wanted to use that method to get data. But currently
                we get data via the local UDP broadcasts.
        """

    def query(self):
        """
                Report status of all nodes
        """
        for node in self.nodes:
            self.nodes[node].reportDrivers()

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

    def delete(self):
        """
        Example
        This is sent by Polyglot upon deletion of the NodeServer.
        """
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
        if 'UDP Port' in self.polyConfig['customParams']:
            self.udp_port = self.polyConfig['customParams']['UDP Port']
        else:
            self.udp_port = default_port

        if 'Units' in self.polyConfig['customParams']:
            self.units = self.polyConfig['customParams']['Units']
        else:
            self.units = default_units

        if 'Elevation' in self.polyConfig['customParams']:
            self.elevation = self.polyConfig['customParams']['Elevation']
        else:
            self.elevation = default_elevation

        # Make sure they are in the params
        self.addCustomParam({'UDP Port': self.udp_port,
                    'Units': self.units,
                    'Elevation': self.elevation})

        # TODO: Is this where we need to set all the node id's and
        #       update the nodes to use the right nodedefs?

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
            data = json.loads(hub[0]) # hub is a truple (json, ip, port)

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


            if (data["type"] == "obs_sky"):
                # process sky data
                il = data['obs'][0][1]  # Illumination
                uv = data['obs'][0][2]  # UV Index
                rr = data['obs'][0][3]  # rain
                wl = data['obs'][0][4] * (18 / 5) # wind lull
                ws = data['obs'][0][5] * (18 / 5) # wind speed
                wg = data['obs'][0][6] * (18 / 5) # wind gust
                wd = data['obs'][0][7]  # wind direction
                sr = data['obs'][0][10]  # solar radiation

                windspeed = ws

                self.nodes['wind'].setDriver('ST', ws)
                self.nodes['wind'].setDriver('GV0', wd)
                self.nodes['wind'].setDriver('GV1', wg)
                #self.nodes['wind'].setDriver('GV2', d['windgustdir'])
                self.nodes['wind'].setDriver('GV3', wl)

                self.nodes['light'].setDriver('ST', uv)
                self.nodes['light'].setDriver('GV0', sr)

                self.nodes['rain'].setDriver('ST', rr)
                #TODO: track daily rain amount
                #self.nodes['rain'].setDriver('GV1', rd)


    """
    Optional.
    Since the controller is the parent node in ISY, it will actual show up
    as a node.  So it needs to know the drivers and what id it will use.
    The drivers are the defaults in the parent Class, so you don't need
    them unless you want to add to them. The ST and GV1 variables are for
    reporting status through Polyglot to ISY, DO NOT remove them. UOM 2
    is boolean.
    """
    name = 'WeatherFlow hub'
    address = 'hub'
    stopping = False
    #id = 'WeatherFlow'
    id = 'Ambient'
    commands = {
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile,
        'REMOVE_NOTICES_ALL': remove_notices_all
    }
    """
    Hub status information here, maybe?
    Or device battery levels?
    """
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 2},
            {'driver': 'BATLVL', 'value': 0, 'uom': 72}  # battery level
            ]


class TemperatureNode(polyinterface.Node):
    id = 'temperature'
    units = 'us'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 17},
            {'driver': 'GV0', 'value': 0, 'uom': 17}, # feels like
            {'driver': 'GV1', 'value': 0, 'uom': 17}, # dewpoint
            {'driver': 'GV2', 'value': 0, 'uom': 17}, # heat index
            {'driver': 'GV3', 'value': 0, 'uom': 17}  # windchill
            ]

    def SetUnits(self, u):
        units = u
        if (u == 'metric'):  # C
            drivers[0].uom = 4
            drivers[1].uom = 4
            drivers[2].uom = 4
            drivers[3].uom = 4
            drivers[4].uom = 4
            id = 'temperature'
        elif (u == 'uk'):  # C
            drivers[0].uom = 4 
            drivers[1].uom = 4
            drivers[2].uom = 4
            drivers[3].uom = 4
            drivers[4].uom = 4
            id = 'temperatureUK'
        elif (u == 'us'):   # F
            drivers[0].uom = 17
            drivers[1].uom = 17
            drivers[2].uom = 17
            drivers[3].uom = 17
            drivers[4].uom = 17
            id = 'temperatureUS'

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
            value = round((value * 1.8) + 32, 1)  # convert to F
        super(TemperatureNode, self).setDriver(driver, value, report=True, force=True)



class HumidityNode(polyinterface.Node):
    id = 'humidity'
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 22}]

    def setDriver(self, driver, value):
        super(HumidityNode, self).setDriver(driver, value, report=True, force=True)

class PressureNode(polyinterface.Node):
    id = 'pressure'
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 117},  # abs press
            {'driver': 'GV0', 'value': 0, 'uom': 117}, # rel press
            {'driver': 'GV1', 'value': 0, 'uom': 25}  # trend
            ]
    trend = Queue.Queue(maxsize=180) # 3 hours worth of data
    mytrend = []


    def SetUnits(self, u):
        # can we dynmically set the drivers here also?
        # what about the ID, can we dynamically change that to change
        # the node def?
        units = u
        if (u == 'metric'):  # millibar
            drivers[0].uom = 117
            drivers[1].uom = 117
            id = 'pressure'
        elif (u == 'uk'):  # millibar
            drivers[0].uom = 117 
            drivers[1].uom = 117
            id = 'pressureUK'
        elif (u == 'us'):   # inHg
            drivers[0].uom = 23
            drivers[1].uom = 23
            id = 'pressureUS'

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
            value *= 0.02952998751
        super(PressureNode, self).setDriver(driver, value, report=True, force=True)


class WindNode(polyinterface.Node):
    id = 'wind'
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
            drivers[0].uom = 32
            drivers[2].uom = 32
            drivers[4].uom = 32
            id = 'wind'
        elif (u == 'uk'): 
            drivers[0].uom = 48
            drivers[2].uom = 48
            drivers[4].uom = 48
            id = 'windUK'
        elif (u == 'us'): 
            drivers[0].uom = 48
            drivers[2].uom = 48
            drivers[4].uom = 48
            id = 'windUS'

    def setDriver(self, driver, value):
        if (driver == 'ST' or driver == 'GV1' or driver == 'GV3'):
            if (self.units != 'metric'):
                value = round(value / 1.609344, 2)
        super(WindNode, self).setDriver(driver, value, report=True, force=True)

class PrecipitationNode(polyinterface.Node):
    id = 'precipitation'
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 24},  # rate
            {'driver': 'GV0', 'value': 0, 'uom': 105}, # daily
            ]
    daily_rain = 0
    weekly_rain = 0
    monthly_rain = 0
    yearly_rain = 0

    def SetUnits(self, u):
        self.units = u
        if (u == 'metric'):
            drivers[0].uom = 82
            drivers[1].uom = 82
            id = 'precipitation'
        elif (u == 'uk'): 
            drivers[0].uom = 82
            drivers[1].uom = 82
            id = 'precipitationUK'
        elif (u == 'us'): 
            drivers[0].uom = 24
            drivers[1].uom = 105
            id = 'precipitationUS'

    def setDriver(self, driver, value):
        super(PrecipitationNode, self).setDriver(driver, value, report=True, force=True)

class LightNode(polyinterface.Node):
    id = 'light'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 71},  # UV
            {'driver': 'GV0', 'value': 0, 'uom': 74},  # solar radiation
            {'driver': 'GV1', 'value': 0, 'uom': 36},  # Lux
            ]

    def setDriver(self, driver, value):
        super(LightNode, self).setDriver(driver, value, report=True, force=True)

class LightningNode(polyinterface.Node):
    id = 'lightning'
    units = 'metric'
    drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 25},  # Strikes
            {'driver': 'GV0', 'value': 0, 'uom': 83},  # Distance
            ]

    def SetUnits(self, u):
        self.units = u
        if (u == 'metric'):
            drivers[0].uom = 83
            id = 'lighning'
        elif (u == 'uk'): 
            drivers[0].uom = 115
            id = 'lighningUK'
        elif (u == 'us'): 
            drivers[0].uom = 115
            id = 'lighningUS'

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
