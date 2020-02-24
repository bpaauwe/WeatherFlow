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

# How do we do some initialization when the class object is created?
# can we manuipulate the node somewhat here?

class HubNode(polyinterface.Node):
    # we want drivers to be dynamically created, is that possible?
    # can we override the default init?
    drivers = []
    hint = [1,11,0,0]
    address = ''
    name = ''
    primary = ''

    def __init__(self, controller, primary, address, name, devices):
        LOGGER.error('In Hub node init.....')
        self.tempest = False
        for device in devices:
            if 'SK' in device:
                LOGGER.error('add sky battery and RSSI')
                HubNode.drivers.append({'driver': 'GV1', 'value': 0, 'uom': 72})
                HubNode.drivers.append({'driver': 'GV3', 'value': 0, 'uom': 56})
                HubNode.drivers.append({'driver': 'GV13', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV14', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV15', 'value': 0, 'uom': 25})
                HubNode.id = 'hub0'
            if 'AR' in device:
                LOGGER.error('add air battery and RSSI')
                HubNode.drivers.append({'driver': 'GV0', 'value': 0, 'uom': 72})
                HubNode.drivers.append({'driver': 'GV2', 'value': 0, 'uom': 56})
                HubNode.drivers.append({'driver': 'GV7', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV8', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV9', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV10', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV11', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV12', 'value': 0, 'uom': 25})
                HubNode.id = 'hub1'
            if 'ST' in device:
                LOGGER.error('add tempest battery and RSSI')
                HubNode.drivers.append({'driver': 'GV5', 'value': 0, 'uom': 72})
                HubNode.drivers.append({'driver': 'GV6', 'value': 0, 'uom': 56})
                HubNode.id = 'hub2'
                self.tempest = True

                HubNode.drivers.append({'driver': 'GV7', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV8', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV9', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV10', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV11', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV12', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV13', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV14', 'value': 0, 'uom': 25})
                HubNode.drivers.append({'driver': 'GV15', 'value': 0, 'uom': 25})
        LOGGER.error(HubNode.drivers)

        # call the default init
        super(HubNode, self).__init__(controller, primary, address, name)


    def SetUnits(self, u):
        self.units = u

    def setDriver(self, driver, value):
        super(HubNode, self).setDriver(driver, value, report=True, force=True)

    def update_rssi(self, rssi_1=None, rssi_2=None):
        if self.tempest:
            self.setDriver('GV6', rssi_1)
        else:
            if rssi_2 is not None:
                self.setDriver('GV3', rssi_2)
            if rssi_1 is not None:
                self.setDriver('GV2', rssi_1)

    # updates the voltage(s)
    def update(self, v1=None, v2=None):
        if self.tempest:
            self.setDriver('GV5', v1)
        else:
            if v1 is not None:
                self.setDriver('GV0', v1)
            if v2 is not None:
                self.setDriver('GV1', v2)


    def update_sensors(self, status):
        if (status & 0x0001) == 0x0001:
            self.setDriver('GV7', 1)
        else:
            self.setDriver('GV7', 0)

        if (status & 0x0002) == 0x0002:
            self.setDriver('GV8', 1)
        else:
            self.setDriver('GV8', 0)

        if (status & 0x0004) == 0x0004:
            self.setDriver('GV9', 1)
        else:
            self.setDriver('GV9', 0)

        if (status & 0x0008) == 0x0008:
            self.setDriver('GV10', 1)
        else:
            self.setDriver('GV10', 0)

        if (status & 0x0010) == 0x0010:
            self.setDriver('GV11', 1)
        else:
            self.setDriver('GV11', 0)

        if (status & 0x0020) == 0x0020:
            self.setDriver('GV12', 1)
        else:
            self.setDriver('GV12', 0)

        if (status & 0x0040) == 0x0040:
            self.setDriver('GV13', 1)
        else:
            self.setDriver('GV13', 0)

        if (status & 0x0080) == 0x0080:
            self.setDriver('GV14', 1)
        else:
            self.setDriver('GV14', 0)

        if (status & 0x0100) == 0x0100:
            self.setDriver('GV15', 1)
        else:
            self.setDriver('GV15', 0)

