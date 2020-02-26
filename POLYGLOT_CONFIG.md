## Configuration

The WeatherFlow node server has the following user configuration parameters:

- ListenPort [required] : Port to listen on for WeatherFlow data. Default is port 50222.
- Station [required]: Your WeatherFlow station ID. Used to query WeatherFlow for station information.
- Air S/N [optional]: The serial number of the AIR device to collect data from.
- Sky S/N [optional]: The serial number of the SKY device to collect data from.
- Tempest S/N [optional]: The serial number of the Tempest device to collect data from.
- Units [optional] : Display data in either 'metric', 'US', or 'UK' units.
- AGL [optional]: Distance Air sensor is above ground level (in meters).
- Elevation [optional] : The elevation, above sea level, at your station's location (in meters).

The WeatherFlow station ID is used to query the WeatherFlow servers for 
information about your station. When found, it will set the approprate
devices serial numbers, units, AGL, and Elevation from the station data.

If you are unable to connect to the WeatherFlow servers, the data may be
entered manually.
