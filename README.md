
# weatherflow-polyglot

This is the WeatherFlow Poly for the [Universal Devices ISY994i](https://www.universal-devices.com/residential/ISY) [Polyglot interface](http://www.universal-devices.com/developers/polyglot/docs/) with  [Polyglot V2](https://github.com/Einstein42/udi-polyglotv2) or [Polisy](https://www.universal-devices.com/product/polisy/)
(c) 2018-2020 Robert Paauwe
MIT license.

This node server is intended to support the [WeatherFlow Smart Weather Station](http://www.weatherflow.com/).


## Version 2.0 notice
Version 2 is a major update with changes to the configuration options and 
how the node server operates. The device serial numbers are used to select
which device data to report. Also, support has been added for the new,
soon to be released Tempest weather station.

## Installation

1. Backup Your ISY in case of problems!
   * Really, do the backup, please
2. Go to the Polyglot Store in the UI and install.
3. From the Polyglot menu, Add NodeServer in Polyglot Web
4. From the Polyglot dashboard, select WeatherFlow node server and configure (see configuration options below).
5. Once configured, the WeatherFlow node server should update the ISY with the proper nodes and begin filling in the node data. Note that it can take up to 1 minute for data to appear.
6. Restart the Admin Console so that it can properly display the new node server nodes.

### Node Settings
The settings for this node are:

#### Short Poll
   * Not used
#### Long Poll
   * Sends a heartbeat as DON/DOF
#### Station
   * The WeatherFlow station ID.
#### ListenPort
   * Port to listen on for WeatherFlow data. Default is port 50222.
#### Sky/Air/Tempest Serial Numbers
   * Specifies the specific sensor devices to monitor. Currently only one
     station can be monitored. This may be a station with a single Air and a
	 Single Sky or a station with a single Tempest.
#### AGL
   * Height of the Air or Tempest above ground level.
#### Elevation
   * Elevation of the location where the station is sited.
#### Units
   * Display data in either 'metric', 'US', or 'UK' units.


## Requirements

1. Polyglot V2 itself should be run on Raspian Stretch.
  To check your version, ```cat /etc/os-release``` and the first line should look like
  ```PRETTY_NAME="Raspbian GNU/Linux 9 (stretch)"```. It is possible to upgrade from Jessie to
  Stretch, but I would recommend just re-imaging the SD card.  Some helpful links:
   * https://www.raspberrypi.org/blog/raspbian-stretch/
   * https://linuxconfig.org/raspbian-gnu-linux-upgrade-from-jessie-to-raspbian-stretch-9
2. ISY firmware 5.0.x or later.

# Upgrading

Open the Polyglot web page, go to nodeserver store and click "Update" for "WeatherFlow".

Then restart the WeatherFlow nodeserver by selecting it in the Polyglot dashboard and select Control -> Restart, then watch the log to make sure everything goes well.

The WeatherFlow nodeserver keeps track of the version number and when a profile rebuild is necessary.  The profile/version.txt will contain the WeatherFlow profile_version which is updated in server.json when the profile should be rebuilt.

# Release Notes

- 2.0.4 03/19/2020
  - Add additional error messages and debugging
- 2.0.3 02/28/2020
  - Fix data update for sky and air
  - Only delete sensor node when station changes.
- 2.0.2 02/27/2020
  - Make better use of the user units configuration
  - Improve field labeling for sensor status values
  - Restrict device list to one device of each type
- 2.0.1 02/26/2020
  - Fix startup sequence to only call discover once
  - Fix log level save/restore
- 2.0.0 02/26/2020
  - Add support for Tempest weather station.
  - Only process data packets that match station device serial numbers.
  - Add configurable log level.
  - Add new node with phyical sensor status.
- 0.1.18 02/11/2020
  - Trap the condition when wind speeds are none/null
- 0.1.17 10/29/2018
  - Add rain yesterday to rain node.
  - Ignore duplicate UDP packets.
- 0.1.16 10/22/2018
  - Clean up debugging log output
  - Add specific debug output of all raw rain values
- 0.1.15 10/19/2018
  - Fix pressure trend (at least during initial 3 hour window)
  - Reverse relative and absolut pressure values, the were mixed up.
- 0.1.14 10/18/2018
  - Add station id configuration option
  - Using station id, query WF servers for station elevation, Air height
    above ground, and user's unit preferences.
  - Add configuration option for Air sensor height above ground
- 0.1.13 10/17/2018
  - Use entered elevation for sealevel pressure calulation
- 0.1.12 10/16/2018
  - Fix typo in sea level pressure calculation
  - Add error checking to dewpoint calculation
- 0.1.11 10/15/2018
  - Change weekly rain accumulation to use week number instead of day of week.
  - Hourly rain was not reseting at begining of next hour
  - Clear old rain accumulations on restart
  - Fix pressure trend values, the values didn't match the NLS names.
  - Don't convert pressure trend when US units are selected, trying to do
    a mb -> inHg conversion on the trend value doesn't make sense.
- 0.1.10 10/09/2018
  - Add error checking to units entry.
  - Add configuration help text
- 0.1.9 10/04/2018
  - Set hint correctly
  - Fix bug with UDP thread start. 
- 0.1.8 09/16/2018
  - JimBo: Send DON/DOF for heartbeat
  - JimBo: Set initial Controller ST default to 1
  - JimBo: Set Hub Seconds Since Seen
- 0.1.7 09/26/2018
   - Add some error trapping in the config change handler
   - Make sure the configuration values are set before trying to use them
   - Fix bug in restoring rain accumulation.
   - Changed order of node creation so that nodes get added with the correct units.
- 0.1.6 09/25/2018
   - Fix bug in rain accumulation.
- 0.1.5 09/11/2018
   - Fix bug in UDP JSON parsing related to migration to python3
- 0.1.4 09/10/2018
   - Convert this to a python program instead of a node.js program
- 0.1.3 09/04/2018
   - Fix bug in NodeDef selections. 
- 0.1.2 07/10/2018
   - Add logging for the UDP port number used.
   - Add error trapping and logging for the UDP socket connection
- 0.1.1 05/08/2018
   - Add ListenPort option to change port we listen on for WeatherFlow data.
- 0.1.0 04/18/2018
   - Initial version published in the Polyglot node server store

- 0.0.1 04/15/2018
   - Initial version published to github
