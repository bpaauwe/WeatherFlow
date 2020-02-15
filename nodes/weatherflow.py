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
import node_funcs
from nodes import temperature
from nodes import humidity
from nodes import pressure
from nodes import rain
from nodes import wind
from nodes import light
from nodes import lightning

LOGGER = polyinterface.LOGGER

@node_funcs.add_functions_as_methods(node_funcs.functions)
class Controller(polyinterface.Controller):
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.name = 'WeatherFlow'
        self.address = 'hub'
        self.primary = self.address
        self.stopping = False
        self.stopped = True
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
                'yesterday': 0,
                }
        self.hb = 0
        self.hub_timestamp = 0
        self.poly.onConfig(self.process_config)
        self.poly.onStop(self.my_stop)
        self.devices = []
        self.params = node_funcs.NSParameters([{
            'name': 'Station',
            'default': 'set me',
            'isRequired': True,
            'notice': 'Station ID must be set',
            },
            {
            'name': 'ListenPort',
            'default': 50222,
            'isRequired': False,
            'notice': '',
            },
            {
            'name': 'Sky S/N',
            'default': '',
            'isRequired': False,
            'notice': '',
            },
            {
            'name': 'Air S/N',
            'default': '',
            'isRequired': False,
            'notice': '',
            },
            {
            'name': 'Tempest S/N',
            'default': '',
            'isRequired': False,
            'notice': '',
            },
            {
            'name': 'Units',
            'default': 'us',
            'isRequired': False,
            'notice': '',
            },
            {
            'name': 'Elevation',
            'default': 0,
            'isRequired': False,
            'notice': '',
            },
            {
            'name': 'AGL',
            'default': 0,
            'isRequired': False,
            'notice': '',
            },
            ])

    def process_config(self, config):
        (valid, changed) = self.params.update_from_polyglot(config)
        if changed and not valid:
            LOGGER.debug('-- configuration not yet valid')
            self.removeNoticesAll()
            self.params.send_notices(self)
        elif changed and valid:
            LOGGER.debug('-- configuration is valid')
            self.removeNoticesAll()
            self.configured = True
            if self.params.isSet('Station'):
                self.discover()
        elif valid:
            LOGGER.debug('-- configuration not changed, but is valid')

    def query_wf(self):
        """
        We need to call this after we get the customParams because
        we need the station number. However, we may want some of the
        data here to override user entered data.  Specifically, elevation
        and units.
        """
        if self.params.get('Station') == "":
            LOGGER.info('no station defined, skipping lookup.')
            return

        path_str = '/swd/rest/stations/'
        path_str += self.params.get('Station')
        path_str += '?api_key=6c8c96f9-e561-43dd-b173-5198d8797e0a'

        try:
            http = urllib3.HTTPConnectionPool('swd.weatherflow.com', maxsize=1)

            # Get station meta data. We really want AIR height above ground
            c = http.request('GET', path_str)
            awdata = json.loads(c.data.decode('utf-8'))
            for station in awdata['stations']:
                LOGGER.info('found station: ' + str(station['location_id']) + ' ' + station['name'])
                if str(station['location_id']) == str(self.params.get('Station')):
                    LOGGER.debug(station)
                    LOGGER.debug('-----------------------------------')
                    LOGGER.debug(station['devices'])
                    self.params.set('Elevation', float(station['station_meta']['elevation']))
                    for device in station['devices']:
                        LOGGER.info('  ' + device['serial_number'] + ' -- ' + device['device_type'])
                        self.devices.append(device['serial_number'])
                        if device['device_type'] == 'AR':
                            self.params.set('Air S/N', device['serial_number'])
                            self.params.set('AGL', float(device['device_meta']['agl']))
                        elif device['device_type'] == 'ST':
                            self.params.set('Tempest S/N', device['serial_number'])
                            self.params.set('AGL', float(device['device_meta']['agl']))
                        elif device['device_type'] == 'SK':
                            self.params.set('Sky S/N', device['serial_number'])


                else:
                    LOGGER.info('skipping station')

            c.close()

            # Get station observations. Pull Elevation and user unit prefs.
            path_str = '/swd/rest/observations/station/'
            path_str += self.params.get('Station')
            path_str += '?api_key=6c8c96f9-e561-43dd-b173-5198d8797e0a'
            c = http.request('GET', path_str)

            awdata = json.loads(c.data.decode('utf-8'))

            # TODO: check user preference for units and set accordingly
            # Check distance & temp
            # if dist in miles & temp in F == US
            # if dist in miles & temp in C == UK
            # else == metric
            temp_unit = awdata['station_units']['units_temp']
            dist_unit = awdata['station_units']['units_distance']

            if temp_unit == 'f' and dist_unit == 'mi':
                LOGGER.info('WF says units are US')
                self.params.set('Units', 'us')
            elif temp_unit == 'c' and dist_unit == 'mi':
                LOGGER.info('WF says units are UK')
                self.params.set('Units', 'uk')
            else:
                LOGGER.info('WF says units are metric')
                self.params.set('Units', 'metric')

            # Override entered elevation with info from station
            # TODO: Only override if current value is 0?
            #       if we do override, should this save to customParams too?
            #self.elevation = float(awdata['elevation'])

            # obs is array of dictionaries. Array index 0 is what we want
            # to get current daily and yesterday daily rainfall values

            LOGGER.info('daily rainfall = %f' %
                    awdata['obs'][0]['precip_accum_local_day'])
            LOGGER.info('yesterday rainfall = %f' %
                    awdata['obs'][0]['precip_accum_local_yesterday'])
            c.close()

            http.close()

            self.params.save_params(self)
        except Exception as e:
            LOGGER.error('Bad: %s' % str(e))


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

        node = temperature.TemperatureNode(self, self.address, 'temperature', 'Temperatures')
        node.SetUnits(self.params.get('Units'))
        self.addNode(node)

        node = humidity.HumidityNode(self, self.address, 'humidity', 'Humidity')
        node.SetUnits(self.params.get('Units'))
        self.addNode(node)
        node = pressure.PressureNode(self, self.address, 'pressure', 'Barometric Pressure')
        node.SetUnits(self.params.get('Units'))
        self.addNode(node)
        node = wind.WindNode(self, self.address, 'wind', 'Wind')
        node.SetUnits(self.params.get('Units'))
        self.addNode(node)
        node = rain.PrecipitationNode(self, self.address, 'rain', 'Precipitation')
        node.SetUnits(self.params.get('Units'))
        self.addNode(node)
        node = light.LightNode(self, self.address, 'light', 'Illumination')
        node.SetUnits(self.params.get('Units'))
        self.addNode(node)
        node = lightning.LightningNode(self, self.address, 'lightning', 'Lightning')
        node.SetUnits(self.params.get('Units'))
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
                self.rain_data['yesterday'] = self.polyConfig['customData']['yesterday']
            except: 
                self.rain_data['hourly'] = 0
                self.rain_data['daily'] = 0
                self.rain_data['weekly'] = 0
                self.rain_data['monthly'] = 0
                self.rain_data['yearly'] = 0
                self.rain_data['yesterday'] = 0
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
        self.removeNoticesAll()

        if self.params.get_from_polyglot(self):
            LOGGER.debug('All required parameters are set!')
            self.configured = True
        else:
            LOGGER.debug('Configuration required.')
            LOGGER.debug('Station = ' + self.params.get('Station'))
            self.params.send_notices(self)

    def remove_notices_all(self,command):
        LOGGER.info('remove_notices_all:')
        # Remove all existing notices
        self.removeNoticesAll()

    def update_profile(self,command):
        LOGGER.info('update_profile:')
        st = self.poly.installprofile()
        return st

    def update_rain(self, ra):
        rain = self.nodes['rain']
        rr = (ra * 60) / it
        rain.setDriver('ST', rr)

        self.rain_data['hourly'] = rain.hourly_accumulation(ra)
        self.rain_data['daily'] = rain.daily_accumulation(ra)
        self.rain_data['yesterday'] = rain.yesterday_accumulation()
        self.rain_data['weekly'] = rain.weekly_accumulation(ra)
        self.rain_data['monthly'] = rain.monthly_accumulation(ra)
        self.rain_data['yearly'] = rain.yearly_accumulation(ra)
        LOGGER.debug('RAIN %f %f %f %f %f %f %f' %
            (ra, rr, self.rain_data['hourly'],
                    self.rain_data['daily'], self.rain_data['weekly'],
            self.rain_data['monthly'], self.rain_data['yearly']))

        self.rain_data['hour'] = datetime.datetime.now().hour
        self.rain_data['day'] = datetime.datetime.now().day
        self.rain_data['month'] = datetime.datetime.now().month
        self.rain_data['year'] = datetime.datetime.now().year

        rain.setDriver('GV0', self.rain_data['hourly'])
        rain.setDriver('GV1', self.rain_data['daily'])
        rain.setDriver('GV2', self.rain_data['weekly'])
        rain.setDriver('GV3', self.rain_data['monthly'])
        rain.setDriver('GV4', self.rain_data['yearly'])
        rain.setDriver('GV5', self.rain_data['yesterday'])

        self.poly.saveCustomData(self.rain_data)

    def air_data(self, data, air_tm):
        # process air data
        try:
            tm = data['obs'][0][0] # ts
            p = data['obs'][0][1]  # pressure
            t = data['obs'][0][2]  # temp
            h = data['obs'][0][3]  # humidity
            ls = data['obs'][0][4] # strikes
            ld = data['obs'][0][5] # distance

            if air_tm == tm:
                LOGGER.debug('Duplicate AIR observations, ignorning')
                return air_tm

            air_tm = tm
            sl = self.nodes['pressure'].toSeaLevel(p, self.params.get('Elevation') + self.params.get('AGL'))
            trend = self.nodes['pressure'].updateTrend(p)
            self.nodes['pressure'].update(p, sl, trend)
            fl = self.nodes['temperature'].ApparentTemp(t, windspeed/3.6, h)
            dp = self.nodes['temperature'].Dewpoint(t, h)
            hi = self.nodes['temperature'].Heatindex(t, h)
            wc = self.nodes['temperature'].Windchill(t, windspeed)

            self.nodes['temperature'].update(t, fl, dp, hi, wc)
            self.nodes['humidity'].update(h)

            self.nodes['lightning'].update(ls, ld)

            # battery voltage
            self.setDriver('GV0', data['obs'][0][6], report=True, force=True)
        except:
            LOGGER.error('Failure in processing AIR data')

        return air_tm

    def sky_data(self, data, sky_tm):
        # process sky data
        try:
            tm = data['obs'][0][0]  # epoch
            il = data['obs'][0][1]  # Illumination
            uv = data['obs'][0][2]  # UV Index
            ra = float(data['obs'][0][3])  # rain
            if (data['obs'][0][4] is not None):
                wl = data['obs'][0][4] * (18 / 5) # wind lull
            else:
                wl = 0
            if (data['obs'][0][5] is not None):
                ws = data['obs'][0][5] * (18 / 5) # wind speed
            else:
                ws = 0
            if (data['obs'][0][6] is not None):
                wg = data['obs'][0][6] * (18 / 5) # wind gust
            else:
                wg = 0
            wd = data['obs'][0][7]  # wind direction
            it = data['obs'][0][9]  # reporting interval
            sr = data['obs'][0][10]  # solar radiation

            if sky_tm == tm:
                LOGGER.debug('Duplicate SKY observations, ignorning')
                return sky_tm

            sky_tm = tm
            windspeed = ws
            #ra = .58 # just over half a mm of rain each minute
        
            self.nodes['wind'].update(ws, wd, wg, wl)
            self.nodes['light'].update(uv, sr, il)

            self.update_rain(ra)

            self.setDriver('GV1', data['obs'][0][8], report=True, force=True)
        except:
            LOGGER.error('Failure in SKY data')

        return sky_tm

    def tempest_data(self, data, st_tm):
        try:
            tm = data['obs'][0][0]  # ts
            # convert wind speed from m/s to kph
            if (data['obs'][0][1] is not None):
                wl = data['obs'][0][1] * (18 / 5) # wind lull
            else:
                wl = 0
            if (data['obs'][0][2] is not None):
                ws = data['obs'][0][2] * (18 / 5) # wind speed
            else:
                ws = 0
            if (data['obs'][0][3] is not None):
                wg = data['obs'][0][3] * (18 / 5) # wind gust
            else:
                wg = 0
            wd = data['obs'][0][4]  # wind direction
            p = data['obs'][0][6]   # pressure
            t = data['obs'][0][7]   # temp
            h = data['obs'][0][8]   # humidity
            il = data['obs'][0][9]  # Illumination
            uv = data['obs'][0][10] # UV Index
            sr = data['obs'][0][11] # solar radiation
            ra = float(data['obs'][0][12])  # rain
            ls = data['obs'][0][14] # strikes
            ld = data['obs'][0][15] # distance
            it = data['obs'][0][17] # reporting interval

            if st_tm == tm:
                LOGGER.debug('Duplicate Tempest observations, ignorning')
                return st_tm

            st_tm = tm

            sl = self.nodes['pressure'].toSeaLevel(p, self.params.get('Elevation') + self.params.get('AGL'))
            trend = self.nodes['pressure'].updateTrend(p)
            fl = self.nodes['temperature'].ApparentTemp(t, ws, h)
            dp = self.nodes['temperature'].Dewpoint(t, h)
            hi = self.nodes['temperature'].Heatindex(t, h)
            wc = self.nodes['temperature'].Windchill(t, ws)

            self.nodes['pressure'].update(p, sl, trend)
            self.nodes['temperature'].update(t, fl, dp, hi, wc)
            self.nodes['humidity'].update(h)
            self.nodes['lightning'].update(ls, ld)
            self.nodes['wind'].update(ws, wd, wg, wl)
            self.nodes['light'].update(uv, sr, il)

            #TODO: add rain
            self.update_rain(ra)

            # battery voltage
            self.setDriver('GV0', data['obs'][0][16], report=True, force=True)
        except:
            LOGGER.error('Failure in TEMPEST data')

        return st_tm

    def udp_data(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', self.params.get('ListenPort')))
        windspeed = 0
        sky_tm = 0
        air_tm = 0
        st_tm  = 0

        LOGGER.info("Starting UDP receive loop")
        while self.stopping == False:
            self.stopped = False
            try:
                hub = s.recvfrom(1024)
                data = json.loads(hub[0].decode("utf-8")) # hub is a truple (json, ip, port)
            except:
                LOGGER.error('JSON processing of data failed')
                continue

            # skip data that's not for the configured station
            if data['serial_number'] not in self.devices:
                LOGGER.info('skipping data, serial number ' + data['serial_number'] + ' not listed')
                continue

            if (data["type"] == "obs_air"):
                air_tm = self.air_data(data, air_tm)

            if (data["type"] == "obs_st"):
                st_tm = self.tempest_data(data, st_tm)

            if (data["type"] == "obs_sky"):
                sky_tm = self.sky_data(data, sky_tm)

            if (data["type"] == "device_status"):
                if "AR" in data["serial_number"]:
                    self.setDriver('GV2', data['rssi'], report=True, force=True)
                if "SK" in data["serial_number"]:
                    self.setDriver('GV3', data['rssi'], report=True, force=True)
                if "ST" in data["serial_number"]:
                    self.setDriver('GV2', data['rssi'], report=True, force=True)

            if (data["type"] == "hub_status"):
                # This comes every 10 seconds, but we only update the driver
                # during longPoll, so just save it.
                #LOGGER.debug("hub_status: time={} {}".format(time.time(),data))
                if "timestamp" in data:
                    self.hub_timestamp = data['timestamp']

        s.close()
        self.stopped = True
        self.stop()

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


