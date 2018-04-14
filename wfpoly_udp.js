//use strict;
const dgram = require('dgram');

module.exports = class WFUDP {
	constructor () {
		this.port = 50222;
		this.opts = {type: 'udp4', reuseAddr: true};
		this.handleAir = null;
		this.handleSky = null;
	}

	Start() {
		this.socket = dgram.createSocket(this.opts);
		this.socket.bind(this.port);

		var air = this.handleAir;
		var sky = this.handleSky;

		this.socket.on('message', function (data, info, error){
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
						if (air && typeof(air) === "function")
							air(J);
						else
							console.log("No callback function for air");
					break;
					case 'obs_sky':
						// Add a callback to handle the data
						console.log("Got Sky Observations");
						if (sky != null)
							sky(J);
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
}

