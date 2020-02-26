#!/usr/bin/env python3
"""
Polyglot v2 node server for WeatherFlow Weather Station data.
Copyright (c) 2018,2019 Robert Paauwe
"""
import polyinterface
import sys
import time
import datetime
import threading
from nodes import weatherflow

LOGGER = polyinterface.LOGGER

if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface('WeatherFlow')
        polyglot.start()
        control = weatherflow.Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
