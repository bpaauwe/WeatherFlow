//use strict;
const dgram = require('dgram');

module.exports = class WFUDP {
	constructor (log) {
		this.port = 50222;
		this.opts = {type: 'udp4', reuseAddr: true};
		this.handleAir = null;
		this.handleSky = null;
		this.airData = {};
		this.skyData = {};
		this.elevation = 0;
		this.trend = [];
		this.log = log;
	}

	Start() {
		this.socket = dgram.createSocket(this.opts);
		this.socket.bind(this.port);

		var air = this.handleAir;
		var sky = this.handleSky;

		//this.socket.on('message', function (data, info, error){
		this.socket.on('message', (data, info, error) => {
			if (error) {
				console.log(error.message);
			} else {
				try {
					var J = JSON.parse(data);
				}
				catch(e) {
					console.log(e.message);
					return;
				};

				switch (J.type) {
					case 'hub_status':
						break;
					case 'device_status':
						break;
					case 'obs_air':
						// Add a callback to handle the data
						console.log("Got Air Observations");
						this.AirCalcs(J);
						if (air && typeof(air) === "function")
							air(this.airData);
						else
							console.log("No callback function for air");
					break;
					case 'obs_sky':
						// Add a callback to handle the data
						console.log("Got Sky Observations");
						this.SkyCalcs(J);
						if (sky != null)
							sky(this.skyData);
						else
							console.log("No callback function for sky");
						break;
					case 'evt_precip':
						break;
					case 'evt_strike':
						break;
					case 'rapid_wind':
						break;
					case 'wind_debug':
						break;
					case 'light_debug':
						break;
					case 'obs_tower':
						break;
					default:
						console.log(J.type + ' unknown data type');
				}
			}
		});

		this.socket.on('listening', function(error) {
			if (error) {
				console.log(error.message);
			} else {
				var address = this.address();
				console.log('Listening on: ' + address.address + ':' + address.port);
			}
		});
	}

	set Air (airhandler) {
		this.handleAir = airhandler;
	}

	set Sky (skyhandler) {
		this.handleSky = skyhandler;
	}

	set Elevation(e) {
		this.elevation = e;
	}

	// Build a new air object with calculated data.
	AirCalcs(j) {
		this.airData['serial_number'] = j.serial_number;
		this.airData['hub_sn'] = j.hub_sn;
		this.airData['firmware_revision'] = j.firmware_revision;
		this.airData['epoch'] = j.obs[0][0];
		this.airData['pressure'] = {
			value: (Number(j.obs[0][1]) * 0.02952998751).toFixed(3), uom: 23 };
		this.airData['temperature'] = { value: Number(j.obs[0][2]), uom: 4 };
		this.airData['humidity'] = { value: Number(j.obs[0][3]), uom: 22 };
		this.airData['strikes'] = { value: Number(j.obs[0][4]), uom: 25 };
		this.airData['strike_distance'] = {
			value: Number(j.obs[0][5]), uom: 83 };
		this.airData['battery'] = { value: Number(j.obs[0][6]), uom: 72 };
		this.airData['interval'] = Number(j.obs[0][7]);
		this.airData['dewpoint'] = {
			value: this.CalcDewPoint(this.airData.temperature.value,
									 this.airData.humidity.value).toFixed(2),
									 uom: 4 };
		var sealevel = this.CalcSeaLevel((j.obs[0][1] * 0.0295299875),
									this.elevation);
		this.airData['sealevel'] = { value: sealevel.toFixed(3), uom: 23 };
		this.airData['trend'] = {
			value: Number(this.PressureTrend(j.obs[0][1])), uom: 25 };

		if (this.skyData.wind_speed !== undefined) {
			this.airData['apparent_temp'] = {
				value: this.CalcApparentTemp(this.airData.temperature.value,
											 this.skyData.wind_speed.value,
											 this.airData.humidity.value).toFixed(2),
											 uom: 4 };
		} else {
			this.airData['apparent_temp'] = { value: 0, uom: 4 };
		}

	}

	// build a new sky object with calculated data.
	SkyCalcs(j) {
		var now = new Date();
		var midnight = new Date();
		midnight.setHours(24,0,0,0); // Next midnight
		//
		// Reset daily rain at midnight
		if (now == midnight)
			this.skyData['rain_daily'] = { value: 0, uom: 82 };
		else
			if (this.skyData['rain_daily'] === undefined)
				this.skyData['rain_daily'] = { value: 0, uom: 82 };


		this.skyData['serial_number'] = j.serial_number;
		this.skyData['hub_sn'] = j.hub_sn;
		this.skyData['firmware_revision'] = j.firmware_revision;
		this.skyData['epoch'] = j.obs[0][0];
		this.skyData['illuminance'] = { value: Number(j.obs[0][1]), uom: 36 };
		this.skyData['uv'] = { value: Number(j.obs[0][2]), uom: 71 };
		this.skyData['rain'] = { value: Number(j.obs[0][3]), uom: 82 };
		this.skyData['lull_speed'] = { value: (Number(j.obs[0][4]) * (18 / 5)).toFixed(2), uom: 32 };
		this.skyData['wind_speed'] = { value: (Number(j.obs[0][5]) * (18 / 5)).toFixed(2), uom: 32 };
		this.skyData['gust_speed'] = { value: (Number(j.obs[0][6]) * (18 / 5)).toFixed(2), uom: 32 };
		this.skyData['wind_direction'] = { value: Number(j.obs[0][7]), uom: 14 };
		this.skyData['battery'] = { value: Number(j.obs[0][8]), uom: 72 };
		this.skyData['interval'] = Number(j.obs[0][9]);
		this.skyData['solar_radiation'] = { value: Number(j.obs[0][10]), uom: 74 };
		this.skyData['rain_daily'] = {
			value: (this.skyData.rain_daily.value + this.skyData.rain.value),
			uom: 82 };
		this.skyData['rain_type'] = { value: Number(j.obs[0][12]), uom: 25 };
		this.skyData['wind_interval'] = Number(j.obs[0][13]);

		var rainrate = this.skyData.rain.value * 60;
		if (this.skyData.interval > 0)
			rainrate = rainrate / this.skyData.interval;

		this.skyData['rain_rate'] = { value: rainrate, uom: 46 };
	}

	CalcDewPoint(temp, humidity) {
		var b = (17.625 * temp) / (243.04 + temp);
		var hlog = Math.log(humidity / 100);

		var dp = (243.04 * (hlog + b)) / (17.625 - hlog - b);

		return dp;
	}

	CalcSeaLevel(Ps, e) {
		const i = 287.05;
		const a = 9.80665;
		const r = .0065;
		const s = 1013.25; // pressure at sealeval
		const n = 288.15;  // Temperature

		var l = a / (i * r);
		var c = i * r / a;
		var pa = s / Ps;
		var b = Math.pow(pa, c);
		var u = Math.pow(1 + b * (r * e / n), l);

		return (Ps * u);
	}

	CalcApparentTemp(temp, speed, humidity) {
		// convert windspeed to mph
		var ws = (speed / 2.2368);
		var h = humidity / 100;

		var wv = h * 6.105 * Math.exp(17.27 * temp / (237.7 + temp));
		return (temp + (0.33 * wv) - (0.70 * ws) - 4.0);
	}

	//
	// trend = 2 means rising
	// trend = 1 means steady
	// trend = 0 means falling
	PressureTrend(pressure) {
		this.trend.push(pressure);
		var first = this.trend[0];

		if (this.trend.length > 300)
			this.trend.shift();

		if (first < (pressure + 1))
			return 2;
		else if (first > (pressure - 1))
			return 0;
		else
			return 1;
	}
}

