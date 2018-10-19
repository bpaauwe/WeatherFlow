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
        self.stopping = False
        self.stopped = True
        self.myConfig = {}
        self.rain_data = {
                'hourly': 0,
                'hour' : 0,
                'daily': 0,
                'day': 0,
                'weekly': 0,
                'week': 0,
                'monthly': 0,
                'month': 0,
                'yearly': 0,
                'year': 0,
                }
        self.hb = 0
        self.hub_timestamp = 0
        self.poly.onConfig(self.process_config)
        self.poly.onStop(self.my_stop)
        self.station = ''
        self.agl = 0.0
        self.elevation = 0.0

    def process_config(self, config):
        # This isn't really what the name implies, it is getting called
        # for all non-driver database updates.  It also appears to be called
        # after the database update has occured.  Thus it is pretty much
        # useless for parameter checking.

        # can we just ignore non-parameter changes?
        if self.myConfig == config['customParams']:
            return

        # looks like a parameter changed, so which one?
        new_params = config['customParams']

        if new_params['Units'] != self.myConfig['Units']:
            LOGGER.info('Changed units from %s to %s' %
                    (self.myConfig['Units'], new_params['Units']))
            # Ideally, we'd like to validate the entered units and
            # report some error if they are wrong, but at this point
            # the database has been updated.
            # FIXME: can we call something common to set the units?

            self.units = config['customParams']['Units'].lower()
            if self.units != 'metric' and self.units != 'us' and self.units != 'uk':
                # invalid units
                self.units = 'metric'
                config['customParams']['Units'] = self.units

            for node in self.nodes:
               if (node != 'hub' and node != 'controller'):
                   LOGGER.info("Setting node " + node + " to units " + self.units);
                   self.nodes[node].SetUnits(self.units)
                   self.addNode(self.nodes[node])
               else:
                   LOGGER.info("Skipping node " + node)

        if new_params['Elevation'] != self.myConfig['Elevation']:
            LOGGER.info('Changed elevation from %s to %s' %
                    (self.myConfig['Elevation'], new_params['Elevation']))

        if new_params['ListenPort'] != self.myConfig['ListenPort']:
            LOGGER.info('Changed UDP Port from %s to %s' %
                    (self.myConfig['ListenPort'], new_params['ListenPort']))

        self.myConfig = config['customParams']

    def query_wf(self):
        """
        We need to call this after we get the customParams because
        we need the station number. However, we may want some of the
        data here to override user entered data.  Specifically, elevation
        and units.
        """
        if self.station == "":
            LOGGER.info('no station defined, skipping lookup.')
            return

        LOGGER.info('Creating URL')
        path_str = '/swd/rest/stations/'
        path_str += self.station
        path_str += '?api_key=6c8c96f9-e561-43dd-b173-5198d8797e0a'
        LOGGER.info('url = %s' % path_str)

        try:
            #http = urllib3.PoolManager()
            http = urllib3.HTTPConnectionPool('swd.weatherflow.com', maxsize=1)

            # Get station meta data
            c = http.request('GET', path_str)
            LOGGER.info('Made request')
            LOGGER.info('%s %s' % (c.status, c.reason))
            #LOGGER.info('data = %s' % c.data)
            awdata = json.loads(c.data.decode('utf-8'))
            #LOGGER.info(awdata['stations'][0]['devices'])
            LOGGER.info('elevation = %f' % awdata['stations'][0]['station_meta']['elevation'])
            for device in awdata['stations'][0]['devices']:
                LOGGER.info('%s %s agl = %s' % (device['device_id'], device['device_type'], device['device_meta']['agl']))
                if device['device_type'] == 'AR':
                    self.agl = float(device['device_meta']['agl'])
            c.close()

            # Get station observations
            path_str = '/swd/rest/observations/station/'
            path_str += self.station
            path_str += '?api_key=6c8c96f9-e561-43dd-b173-5198d8797e0a'
            c = http.request('GET', path_str)
            LOGGER.info('%s %s' % (c.status, c.reason))

            #LOGGER.info('data = %s' % c.data)
            awdata = json.loads(c.data.decode('utf-8'))

            # TODO: check user preference for units and set accordingly
            LOGGER.info('Units = %s' % awdata['station_units'])
            # Check distance & temp
            # if dist in miles & temp in F == US
            # if dist in miles & temp in C == UK
            # else == metric
            temp_unit = awdata['station_units']['units_temp']
            dist_unit = awdata['station_units']['units_distance']

            if temp_unit == 'f' and dist_unit == 'mi':
                LOGGER.info('WF says units are US')
                self.units = 'us'
            elif temp_unit == 'c' and dist_unit == 'mi':
                LOGGER.info('WF says units are UK')
                self.units = 'uk'
            else:
                LOGGER.info('WF says units are metric')
                self.units = 'metric'

            # Override entered elevation with info from station
            # TODO: Only override if current value is 0?
            #       if we do override, should this save to customParams too?
            LOGGER.info('Elevation = %f' % awdata['elevation'])
            self.elevation = float(awdata['elevation'])

            # We need to query device information to get the height above
            # ground for the air sensor. Do we have the info to get that?


            # obs is array of dictionaries. Array index 0 is what we want
            # to get current daily and yesterday daily rainfall values
            LOGGER.info('keys = %s' % awdata['obs'])

            LOGGER.info('daily = %f' % awdata['obs'][0]['precip_accum_local_day'])
            LOGGER.info('yesterday = %f' % awdata['obs'][0]['precip_accum_local_yesterday'])
        except Exception as e:
            LOGGER.error('Bad: %s' % str(e))

        c.close()
        http.close()

    def start(self):
        LOGGER.info('Starting WeatherFlow Node Server')
        self.check_params()
        self.discover()

        LOGGER.info('starting thread for UDP data')
        self.udp = threading.Thread(target = self.udp_data)
        self.udp.daemon = True
        self.udp.start()

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

        self.query_wf()

        node = TemperatureNode(self, self.address, 'temperature', 'Temperatures')
        node.SetUnits(self.units)
        self.addNode(node)

        node = HumidityNode(self, self.address, 'humidity', 'Humidity')
        node.SetUnits(self.units)
        self.addNode(node)
        node = PressureNode(self, self.address, 'pressure', 'Barometric Pressure')
        node.SetUnits(self.units)
        self.addNode(node)
        node = WindNode(self, self.address, 'wind', 'Wind')
        node.SetUnits(self.units)
        self.addNode(node)
        node = PrecipitationNode(self, self.address, 'rain', 'Precipitation')
        node.SetUnits(self.units)
        self.addNode(node)
        node = LightNode(self, self.address, 'light', 'Illumination')
        node.SetUnits(self.units)
        self.addNode(node)
        node = LightningNode(self, self.address, 'lightning', 'Lightning')
        node.SetUnits(self.units)
        self.addNode(node)

        
        if 'customData' in self.polyConfig:
            try:
                self.rain_data['hourly'] = self.polyConfig['customData']['hourly']
                self.rain_data['daily'] = self.polyConfig['customData']['daily']
                self.rain_data['weekly'] = self.polyConfig['customData']['weekly']
                self.rain_data['monthly'] = self.polyConfig['customData']['monthly']
                self.rain_data['yearly'] = self.polyConfig['customData']['yearly']
                self.rain_data['hour'] = self.polyConfig['customData']['hour']
                self.rain_data['day'] = self.polyConfig['customData']['day']
                self.rain_data['month'] = self.polyConfig['customData']['month']
                self.rain_data['year'] = self.polyConfig['customData']['year']
            except: 
                self.rain_data['hourly'] = 0
                self.rain_data['daily'] = 0
                self.rain_data['weekly'] = 0
                self.rain_data['monthly'] = 0
                self.rain_data['yearly'] = 0
                self.rain_data['hour'] = datetime.datetime.now().hour
                self.rain_data['day'] = datetime.datetime.now().day
                self.rain_data['week'] = datetime.datetime.now().isocalendar()[1]
                self.rain_data['month'] = datetime.datetime.now().month
                self.rain_data['year'] = datetime.datetime.now().year
                # TODO: Can we query the current accumulation data from
                # weatherflow servers???

            self.nodes['rain'].InitializeRain(self.rain_data)

            # Might be able to get some information from API using station
            # number:
            # swd.weatherflow.com/swd/rest/observations/station/<num>?apikey=

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
        self.setDriver('GV4', s, report=True, force=True)

    def delete(self):
        self.stopping = True
        LOGGER.info('Removing WeatherFlow node server.')

    def my_stop(self):
        self.stopping = True
        # Is there something we should do here to really stop?
        while not self.stopped:
            self.stopping = True

        LOGGER.info('WeatherFlow node server UDP thread finished.')

    def stop(self):
        self.stopping = True
        LOGGER.debug('Stopping WeatherFlow node server.')

    def check_units(self):
        if 'Units' in self.polyConfig['customParams']:
            units = self.polyConfig['customParams']['Units'].lower()

            if units != 'metric' and units != 'us' and units != 'uk':
                # invalid units
                units = 'metric'
                self.addCustomParam({'Units': units})
        else:
            units = 'metric'

        return units

    def check_params(self):
        """
        Elevation, UDP port, and Units for now.
        """
        default_port = 50222
        default_elevation = 0.0
        default_units = "metric"

        self.units = self.check_units()

        if 'ListenPort' in self.polyConfig['customParams']:
            self.udp_port = int(self.polyConfig['customParams']['ListenPort'])
        else:
            self.udp_port = default_port
            self.polyConfig['customParams']['ListenPort'] = default_port

        if 'Station' in self.polyConfig['customParams']:
            self.station = self.polyConfig['customParams']['Station']

        if 'AGL' in self.polyConfig['customParams']:
            self.agl = float(self.polyConfig['customParams']['AGL'])

        if 'Elevation' in self.polyConfig['customParams']:
            self.elevation = float(self.polyConfig['customParams']['Elevation'])
        else:
            self.elevation = default_elevation
            self.polyConfig['customParams']['Elevation'] = default_elevation

        self.myConfig = self.polyConfig['customParams']

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
            self.stopped = False
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

                sl = self.nodes['pressure'].toSeaLevel(p, self.elevation + self.agl)
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
                ra = float(data['obs'][0][3])  # rain
                wl = data['obs'][0][4] * (18 / 5) # wind lull
                ws = data['obs'][0][5] * (18 / 5) # wind speed
                wg = data['obs'][0][6] * (18 / 5) # wind gust
                wd = data['obs'][0][7]  # wind direction
                it = data['obs'][0][9]  # reporting interval
                sr = data['obs'][0][10]  # solar radiation

                windspeed = ws
                #ra = .58 # just over half a mm of rain each minute
                
                self.nodes['wind'].setDriver('ST', ws)
                self.nodes['wind'].setDriver('GV0', wd)
                self.nodes['wind'].setDriver('GV1', wg)
                self.nodes['wind'].setDriver('GV2', wd)
                self.nodes['wind'].setDriver('GV3', wl)

                self.nodes['light'].setDriver('ST', uv)
                self.nodes['light'].setDriver('GV0', sr)
                self.nodes['light'].setDriver('GV1', il)

                rain = self.nodes['rain']
                rr = (ra * 60) / it
                rain.setDriver('ST', rr)

                self.rain_data['hourly'] = rain.hourly_accumulation(ra)
                self.rain_data['daily'] = rain.daily_accumulation(ra)
                self.rain_data['weekly'] = rain.weekly_accumulation(ra)
                self.rain_data['monthly'] = rain.monthly_accumulation(ra)
                self.rain_data['yearly'] = rain.yearly_accumulation(ra)

                self.rain_data['hour'] = datetime.datetime.now().hour
                self.rain_data['day'] = datetime.datetime.now().day
                self.rain_data['month'] = datetime.datetime.now().month
                self.rain_data['year'] = datetime.datetime.now().year

                rain.setDriver('GV0', self.rain_data['hourly'])
                rain.setDriver('GV1', self.rain_data['daily'])
                rain.setDriver('GV2', self.rain_data['weekly'])
                rain.setDriver('GV3', self.rain_data['monthly'])
                rain.setDriver('GV4', self.rain_data['yearly'])

                self.poly.saveCustomData(self.rain_data)

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

        s.close()
        self.stopped = True

    def SetUnits(self, u):
        self.units = u


    id = 'WeatherFlow'
    name = 'WeatherFlow'
    address = 'hub'
    stopping = False
    hint = [1, 11, 0, 0]
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
    hint = [1,11,2,0]
    units = 'metric'
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 22}]

    def SetUnits(self, u):
        self.units = u

    def setDriver(self, driver, value):
        super(HumidityNode, self).setDriver(driver, value, report=True, force=True)

class PressureNode(polyinterface.Node):
    id = 'pressure'
    hint = [1,11,3,0]
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

        if len(self.mytrend) == 180:
            # This should be poping the last entry on the list (or the 
            # oldest item added to the list).
            past = self.mytrend.pop()

        if self.mytrend != []:
            # mytrend[0] seems to be the last entry inserted, not
            # the first.  So how do we get the last item from the
            # end of the array -- mytrend[-1]
            past = self.mytrend[-1]
            for i, p in enumerate(self.mytrend):
                LOGGER.info('%d = %f' % (i, p))

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
    prev_month = 0
    prev_year = 0

    def InitializeRain(self, acc):
        self.daily_rain = acc['daily']
        self.hourly_rain = acc['hourly']
        self.weekly_rain = acc['weekly']
        self.monthly_rain = acc['monthly']
        self.yearly_rain = acc['yearly']

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
            self.hourly_rain = 0

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
        if (self.units == 'us'):
            value = round(value * 0.03937, 2)
        super(PrecipitationNode, self).setDriver(driver, value, report=True, force=True)

class LightNode(polyinterface.Node):
    id = 'light'
    units = 'metric'
    hint = [1,11,6,0]
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
    hint = [1,11,7,0]
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
