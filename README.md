
# weatherflow-polyglot

This is the WeatherFlow Poly for the [Universal Devices ISY994i](https://www.universal-devices.com/residential/ISY) [Polyglot interface](http://www.universal-devices.com/developers/polyglot/docs/) with  [Polyglot V2](https://github.com/Einstein42/udi-polyglotv2)
(c) 2018 Robert Paauwe
MIT license.

This node server is intended to support the [WeatherFlow Smart Weather Station](http://www.weatherflow.com/).

## Installation

1. Backup Your ISY in case of problems!
   * Really, do the backup, please
2. Go to the Polyglot Store in the UI and install.
3. Add NodeServer in Polyglot Web
   * After the install completes, Polyglot will reboot your ISY, you can watch the status in the main polyglot log.
4. Once your ISY is back up open the Admin Console.
5. The node server should automatically run and find your hub(s) and start adding weather sensors.  It can take a couple of minutes to discover the sensors. Verify by checking the nodeserver log. 
   * While this is running you can view the nodeserver log in the Polyglot UI to see what it's doing
6. This should find your Air/Sky sensors and add them to the ISY with all the sensor values.

### Node Settings
The settings for this node are:

#### Short Poll
   * This is how often it will update the last update time for each node.
#### Long Poll
   * Sends a heartbeat as DON/DOF
#### Elevation
   * The height of the Air sensor above sea level, in meters.
#### Units
   * Display data in either 'metric', 'US', or 'UK' units.
#### ListenPort
   * Port to listen on for WeatherFlow data. Default is port 50222.


## Requirements

1. Polyglot V2 itself should be run on Raspian Stretch.
  To check your version, ```cat /etc/os-release``` and the first line should look like
  ```PRETTY_NAME="Raspbian GNU/Linux 9 (stretch)"```. It is possible to upgrade from Jessie to
  Stretch, but I would recommend just re-imaging the SD card.  Some helpful links:
   * https://www.raspberrypi.org/blog/raspbian-stretch/
   * https://linuxconfig.org/raspbian-gnu-linux-upgrade-from-jessie-to-raspbian-stretch-9
2. This has only been tested with ISY 5.0.13 so it is not guaranteed to work with any other version.

# Upgrading

Open the Polyglot web page, go to nodeserver store and click "Update" for "WeatherFlow".

For Polyglot 2.0.35, hit "Cancel" in the update window so the profile will not be updated and ISY rebooted.  The install procedure will properly handle this for you.  This will change with 2.0.36, for that version you will always say "No" and let the install procedure handle it for you as well.

Then restart the WeatherFlow nodeserver by selecting it in the Polyglot dashboard and select Control -> Restart, then watch the log to make sure everything goes well.

The WeatherFlow nodeserver keeps track of the version number and when a profile rebuild is necessary.  The profile/version.txt will contain the WeatherFlow profile_version which is updated in server.json when the profile should be rebuilt.

# Release Notes

- 0.1.10 10/09/2018
  - Add error checking to units entry.
  - Add configuration help text
- 0.1.9 10/04/2018
  - Set hint correctly
  - Fix bug with UDP thread start. 
- 0.1.8 09/16/2018
  - JimBo: Send DON/DOF for heartbeta
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
