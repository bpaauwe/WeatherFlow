## Configuration

The WeatherFlow node server has the following user configuration parameters:

- ListenPort [required] : Port to listen on for WeatherFlow data. Default is port 50222.
- Station [optional]: Your WeatherFlow station ID. Used to query WeatherFlow for station information.
- Air S/N [optional]: The serial number of the AIR device to collect data from.
- Sky S/N [optional]: The serial number of the SKY device to collect data from.
- Tempest S/N [optional]: The serial number of the Tempest device to collect data from.
- Units [optional] : Display data in either 'metric', 'US', or 'UK' units.
- AGL [optional]: Distance Air sensor is above ground level (in meters).
- Elevation [optional] : The elevation, above sea level, at your station's location (in meters).

If you specify the the WeatherFlow station ID, an attempt will be made to 
contact the WeatherFlow servers and fill in all the optional parameters for
you.  If don't have an internet connection, you must specify the device
serial numbers.  The AGL and Elevation values are used to calculate the
corrected pressure at your location.
