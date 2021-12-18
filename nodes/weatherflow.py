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
from nodes import hub

LOGGER = polyinterface.LOGGER

@node_funcs.add_functions_as_methods(node_funcs.functions)
class Controller(polyinterface.Controller):
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        # are these overriding the class variables?
        self.name = 'WeatherFlow' 
        self.address = 'wf'
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
                'level': 30,
                'station': '',
                }
        self.hb = 0
        self.hub_timestamp = 0
        self.tempest = False
        self.poly.onConfig(self.process_config)
        self.poly.onStop(self.my_stop)
        self.devices = []
        self.discovered = ""
        self.units = {
                'temperature': 'c',
                'wind': 'kph',
                'pressure': 'mb',
                'rain': 'mm',
                'distance': 'km',
                'other': 'metric',
                }
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
            if self.params.isSet('Station') and (self.discovered != "") and (self.discovered != self.params.get('Station')):
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

        air_found = False
        sky_found = False
        tempest_found = False

        self.devices = []  # clear the devcies array
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
                        if 'serial_number' not in device:
                            LOGGER.error('Bad device record for device ID ' + str(device['device_id']))
                            continue

                        LOGGER.info('  ' + device['serial_number'] + ' -- ' + device['device_type'])
                        if device['serial_number'] not in self.devices:
                            self.devices.append(device['serial_number'])

                        if device['device_type'] == 'AR' and not air_found:
                            self.params.set('Air S/N', device['serial_number'])
                            self.params.set('AGL', float(device['device_meta']['agl']))
                            air_found = True
                            self.Tempest = False
                        elif device['device_type'] == 'ST' and not tempest_found:
                            self.params.set('Tempest S/N', device['serial_number'])
                            self.params.set('AGL', float(device['device_meta']['agl']))
                            tempest_found = True
                            self.Tempest = True
                            device_id = device['device_id']
                        elif device['device_type'] == 'SK' and not sky_found:
                            self.params.set('Sky S/N', device['serial_number'])
                            sky_found = True
                            self.Tempest = False
                            device_id = device['device_id']


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
            self.units['temperature'] = awdata['station_units']['units_temp']
            self.units['wind'] = awdata['station_units']['units_wind']
            self.units['rain'] = awdata['station_units']['units_precip']
            self.units['pressure'] = awdata['station_units']['units_pressure']
            self.units['distance'] = awdata['station_units']['units_distance']
            self.units['other'] = awdata['station_units']['units_other']

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

            d_rain = awdata['obs'][0]['precip_accum_local_day']
            LOGGER.info('daily rainfall = %f' % d_rain)
            p_rain = awdata['obs'][0]['precip_accum_local_yesterday']
            LOGGER.info('yesterday rainfall = %f' % p_rain)
            c.close()

            # Do month by month query of rain info.
            today = datetime.datetime.today()
            y_rain = 0
            for month in range(1,today.month+1):
                try:
                    m_rain = 0
                    # get epoch time for start of month and end of month
                    datem = datetime.datetime(today.year, month, 1)
                    start_date = datem.replace(day=1)
                    #end_date = datem.replace(month=(month+1 % 12), day=1) - datetime.timedelta(days=1)
                    end_date = datem.replace(month=(month+1 % 12), day=1)

                    # make request:
                    #  /swd/rest/observations/device/<id>?time_start=start&time_end=end&api_key=
                    path_str = '/swd/rest/observations/device/'
                    path_str += str(device_id) + '?'
                    path_str += 'time_start=' + str(int(start_date.timestamp()))
                    path_str += '&time_end=' + str(int(end_date.timestamp()))
                    path_str += '&api_key=6c8c96f9-e561-43dd-b173-5198d8797e0a'

                    LOGGER.info('path = ' + path_str)

                    c = http.request('GET', path_str)
                    awdata = json.loads(c.data.decode('utf-8'))

                    # we should now have an array of observations
                    for obs in awdata['obs']:
                        # for sky, index 3 is daily rain.  for tempest it is index 12
                        if sky_found:
                            m_rain += obs[3]
                            y_rain += obs[3]
                        elif tempest_found:
                            m_rain += obs[12]
                            y_rain += obs[12]

                    LOGGER.info('Month ' + str(month) + ' had rain = ' + str(m_rain))

                    c.close()
                except:
                    LOGGER.error('Failed to get rain for month %d' % month);
                    c.close()

            LOGGER.info('yearly rain total = ' + str(y_rain))

            # Need to do a separate query for weekly rain
            start_date = today - datetime.timedelta(days=7)
            end_date = today
            path_str = '/swd/rest/observations/device/'
            path_str += str(device_id) + '?'
            path_str += 'time_start=' + str(int(start_date.timestamp()))
            path_str += '&time_end=' + str(int(end_date.timestamp()))
            path_str += '&api_key=6c8c96f9-e561-43dd-b173-5198d8797e0a'

            LOGGER.info('path = ' + path_str)

            try:
                c = http.request('GET', path_str)
                awdata = json.loads(c.data.decode('utf-8'))
                w_rain = 0
                for obs in awdata['obs']:
                    if sky_found:
                        w_rain += obs[3]
                    elif tempest_found:
                        w_rain += obs[12]

                c.close()
            except:
                LOGGER.error('Failed to get weekly rain')
                c.close()

            LOGGER.info('weekly rain total = ' + str(w_rain))

            http.close()

            if y_rain > 0:
                self.rain_data['yearly'] = y_rain
                self.rain_data['year'] = datetime.datetime.now().year
            if m_rain > 0:
                self.rain_data['monthly'] = m_rain
                self.rain_data['month'] = datetime.datetime.now().month
            if w_rain > 0:
                self.rain_data['weekly'] = w_rain
                self.rain_data['week'] = datetime.datetime.now().isocalendar()[1]
            if d_rain > 0:
                self.rain_data['daily'] = d_rain
                self.rain_data['day'] = datetime.datetime.now().day
            if p_rain > 0:
                self.rain_data['yesterday'] = p_rain

            self.rain_data['hourly'] = 0

            self.params.save_params(self)
        except Exception as e:
            LOGGER.error('Bad: %s' % str(e))


    def start(self):
        LOGGER.info('Starting WeatherFlow Node Server')
        self.set_logging_level()
        self.check_params()
        self.read_custom_data()
        if self.params.isSet('Station'):
            LOGGER.info('Discover station info / create nodes')
            self.discover()

        LOGGER.info('Starting thread for UDP data')
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
        self.discovered = self.params.get('Station')

        node = temperature.TemperatureNode(self, self.address, 'temperature', 'Temperatures')
        node.SetUnits(self.units['temperature'])
        self.addNode(node)

        node = humidity.HumidityNode(self, self.address, 'humidity', 'Humidity')
        node.SetUnits(self.params.get('Units'))
        self.addNode(node)
        node = pressure.PressureNode(self, self.address, 'pressure', 'Barometric Pressure')
        node.SetUnits(self.units['pressure'])
        self.addNode(node)
        node = wind.WindNode(self, self.address, 'wind', 'Wind')
        node.SetUnits(self.units['wind'])
        self.addNode(node)
        node = rain.PrecipitationNode(self, self.address, 'rain', 'Precipitation')
        node.SetUnits(self.units['rain'])
        self.addNode(node)
        node = light.LightNode(self, self.address, 'light', 'Illumination')
        node.SetUnits(self.params.get('Units'))
        self.addNode(node)
        node = lightning.LightningNode(self, self.address, 'lightning', 'Lightning')
        node.SetUnits(self.units['distance'])
        self.addNode(node)

        # TODO: Add hub node with battery and rssi (and sensor status?) info
        #  There are two different hub node ID's, one for air/sky and one
        #  for tempest.  Use self.devices to determine which we want to 
        #  create here.
        #  self.devices[] holds the devices that we want to track.
        # TODO: Wait for hub node to really be deleted.
        if self.rain_data['station'] != self.params.get('Station'):
                LOGGER.info('Station has changed from ' + 
                        self.rain_data['station'] + ' to ' +
                        self.params.get('Station'))
                self.rain_data['station'] = self.params.get('Station')
                self.poly.saveCustomData(self.rain_data)
                LOGGER.debug(self.polyConfig['customData'])

                LOGGER.debug('deleting existing sensor status node')
                self.delNode('hub')
                time.sleep(3)  # give it some time to actually happen

        LOGGER.debug('Attempt to add sensor status node')

        if self.tempest:
            node = hub.HubNode(self, self.address, 'hub', 'Hub', self.devices);
        else:
            node = hub.HubNode(self, self.address, 'hub', 'Hub', self.devices);
        LOGGER.debug('Sensor status node has been created, so add it')
        try:
            self.addNode(node)
        except Exception as e:
            LOGGER.error('Error adding sensor status node: ' + str(e))
        
                # TODO: Can we query the current accumulation data from
                # weatherflow servers???

        self.nodes['rain'].InitializeRain(self.rain_data)

            # Might be able to get some information from API using station
            # number:
            # swd.weatherflow.com/swd/rest/observations/station/<num>?apikey=

    def read_custom_data(self):
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
                self.rain_data['level'] = self.polyConfig['customData']['level']
                self.rain_data['station'] = self.polyConfig['customData']['station']
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

            if self.params.get('Units') == 'us':
                self.units['temperature'] = 'f'
                self.units['wind'] = 'mph'
                self.units['rain'] = 'in'
                self.units['pressure'] = 'inhg'
                self.units['distance'] = 'mi'
                self.units['other'] = 'imperial'
            elif self.params.get('Units') == 'uk':
                self.units['temperature'] = 'c'
                self.units['wind'] = 'mph'
                self.units['rain'] = 'in'
                self.units['pressure'] = 'mb'
                self.units['distance'] = 'mi'
                self.units['other'] = 'imperial'
            else:
                self.units['temperature'] = 'c'
                self.units['wind'] = 'kph'
                self.units['rain'] = 'mm'
                self.units['pressure'] = 'mb'
                self.units['distance'] = 'km'
                self.units['other'] = 'metric'

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

    def update_rain(self, ra, it):
        try:
            rain = self.nodes['rain']
            rr = (ra * 60) / it
            rain.setDriver('ST', rr)
        except Exception as e:
            LOGGER.error(str(e))

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

            LOGGER.debug(data)

            air_tm = tm
            el = float(self.params.get('Elevation')) + float(self.params.get('AGL'))
            sl = self.nodes['pressure'].toSeaLevel(p, el)
            trend = self.nodes['pressure'].updateTrend(p)
            self.nodes['pressure'].update(p, sl, trend)
            try:
                fl = self.nodes['temperature'].ApparentTemp(t, self.windspeed/3.6, h)
                dp = self.nodes['temperature'].Dewpoint(t, h)
                hi = self.nodes['temperature'].Heatindex(t, h)
                wc = self.nodes['temperature'].Windchill(t, self.windspeed)
            except Exception as e:
                LOGGER.error('Failure to calculate Air temps: ' + str(e))

            self.nodes['temperature'].update(t, fl, dp, hi, wc)
            self.nodes['humidity'].update(h)

            self.nodes['lightning'].update(ls, ld)

            # battery voltage
            try:
                self.nodes['hub'].update(data['obs'][0][6], None)
                #self.setDriver('GV0', data['obs'][0][6], report=True, force=True)
            except Exception as e:
                LOGGER.error('Failed to update sky battery voltage: ' + str(e))
        except Exception as e:
            (t, v, tb) = sys.exec_info()
            LOGGER.error('Failure in processing AIR data: ' + str(e))
            LOGGER.error('  At: ' + str(tb.tb_lineno));

        return air_tm

    def sky_data(self, data, sky_tm):
        # process sky data
        try:
            LOGGER.debug(data)

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
            self.windspeed = ws
            #ra = .58 # just over half a mm of rain each minute
        
            self.nodes['wind'].update(ws, wd, wg, wl)
            self.nodes['light'].update(uv, sr, il)

            try:
                self.update_rain(ra, it)
            except Exception as e:
                LOGGER.error('Failed to update rain data: ' + str(e))

            try:
                self.nodes['hub'].update(None, data['obs'][0][8])
                #self.setDriver('GV1', data['obs'][0][8], report=True, force=True)
            except Exception as e:
                LOGGER.error('Failed to update sky battery voltage: ' + str(e))

        except Exception as e:
            (t, v, tb) = sys.exec_info()
            LOGGER.error('Failure in SKY data: ' + str(e))
            LOGGER.error('  At: ' + str(tb.tb_lineno));

        return sky_tm

    def tempest_data(self, data, st_tm):
        try:
            LOGGER.debug(data)

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

            el = float(self.params.get('Elevation')) + float(self.params.get('AGL'))
            sl = self.nodes['pressure'].toSeaLevel(p, el)
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

            self.update_rain(ra, it)

            # battery voltage
            self.nodes['hub'].update(data['obs'][0][16], None)
            #self.setDriver('GV0', data['obs'][0][16], report=True, force=True)

        except Exception as e:
            (t, v, tb) = sys.exec_info()
            LOGGER.error('Failure in TEMPEST data: ' + str(e))
            LOGGER.error('  At: ' + str(tb.tb_lineno));

        return st_tm

    def udp_data(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.bind(('0.0.0.0', self.params.get('ListenPort')))
        self.windspeed = 0
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
                #LOGGER.info('skipping data, serial number ' + data['serial_number'] + ' not listed')
                continue

            if (data["type"] == "obs_air"):
                air_tm = self.air_data(data, air_tm)

            if (data["type"] == "obs_st"):
                st_tm = self.tempest_data(data, st_tm)

            if (data["type"] == "obs_sky"):
                sky_tm = self.sky_data(data, sky_tm)

            if (data["type"] == "device_status"):
                if "AR" in data["serial_number"]:
                    #self.setDriver('GV2', data['rssi'], report=True, force=True)
                    self.nodes['hub'].update_rssi(data['rssi'], None)
                    self.nodes['hub'].update_sensors(data['sensor_status'])
                if "SK" in data["serial_number"]:
                    #self.setDriver('GV3', data['rssi'], report=True, force=True)
                    self.nodes['hub'].update_rssi(None, data['rssi'])
                    self.nodes['hub'].update_sensors(data['sensor_status'])
                if "ST" in data["serial_number"]:
                    #self.setDriver('GV2', data['rssi'], report=True, force=True)
                    self.nodes['hub'].update_rssi(data['rssi'])
                    self.nodes['hub'].update_sensors(data['sensor_status'])

            if (data["type"] == "hub_status"):
                # This comes every 10 seconds, but we only update the driver
                # during longPoll, so just save it.
                #LOGGER.debug("hub_status: time={} {}".format(time.time(),data))
                if "timestamp" in data:
                    self.hub_timestamp = data['timestamp']

        s.close()
        self.stopped = True
        self.stop()

    def set_logging_level(self, level=None):
        if level is None:
            try:
                level = self.get_saved_log_level()
            except:
                LOGGER.error('set_logging_level: get saved log level failed.')

        if level is None:
            level = 30
            level = int(level)
        else:
            level = int(level['value'])

        self.save_log_level(level)

        LOGGER.info('set_logging_level: Setting log level to %d' % level)
        LOGGER.setLevel(level)

    id = 'WeatherFlow'
    name = 'WeatherFlow'
    address = 'wf'
    stopping = False
    hint = [1, 11, 0, 0]
    units = 'metric'
    commands = {
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile,
        'REMOVE_NOTICES_ALL': remove_notices_all,
        'DEBUG': set_logging_level,
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


