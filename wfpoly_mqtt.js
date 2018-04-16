const mqtt = require('mqtt');
const url = require('url');

module.exports = class PolyMQTT {
	constructor (host, port, profile, connected, log) {
		this.host = host;
		this.port = port;
		this.ready = connected;
		this.profile = profile;
		this.client = null;
		this.topic = 'udi/polyglot/ns/' + this.profile;
		this.log = log;
		this.customParams = null;
		this.newParams = null;
	}

	get ConfiguredNodes() {
		this.log("in ConfiguredNodes");
		if (this.config.newNodes !== undefined)
			return this.config.newNodes;
		else if (this.config.nodes !== undefined)
			return this.config.nodes;

		return new Array();
	}

	get Units() {
		if (this.config.customParams.Units !== undefined) {
			return this.config.customParams.Units;
		}
		return 'metric';
	}

	get Elevation() {
		if (this.config.customParams.Elevation !== undefined) {
			return Number(this.config.customParams.Elevation);
		}
		return 0;
	}

	Start() {
		var options = {
			port: this.port,
			clientId: 'mqttjs_' + Math.random().toString(16).substr(2,8),
			username: 'admin',
			password: 'admin',
			rejectUnauthorized: false,
		};
		var _this = this;

		this.client = mqtt.connect(this.host, options);

		this.client.on('error', function() {
			console.log('error making mqtt connection to polyglot');
		});

		this.client.on('connect', function() {
			console.log('connected');
			_this.log('MQTT host connected');
			_this.client.subscribe('udi/polyglot/connections/polyglot');
			_this.client.subscribe('udi/polyglot/connections/' + _this.profile);
			_this.client.subscribe(_this.topic);

			var msg = { node: _this.profile, connected: true };

			_this.Publish(msg);

			// If this.ready is a callback, call it here
			_this.ready.emit('connected', '');
		});

		//this.client.on('message', this.messagehandler);
		//this.client.on('message', function(topic, message) {
		this.client.on('message', (topic, message) => {
			//_this.log("Received message from poly");
			if (topic == 'udi/polyglot/connections/polyglot') {
				console.log(topic + ' sent ' + message);
			} else if (topic == 'udi/polyglot/connections/' + _this.profile) {
				console.log(topic + ' sent ' + message);
			} else if (topic == _this.topic) {
				this.ProcessPolyMsg(message);
			} else {
				console.log(topic + ' unknown ' + message);
			}

			if (JSON.stringify(this.newParams) !== JSON.stringify(this.customParams)) {
				var mesg = { 'customparams': this.newParams,
							 'node': this.profile };
				// Save the params ??
				this.log("Saving updated custom parameters.");
				this.client.publish(this.topic, JSON.stringify(mesg), false);
				this.customParams = this.newParams;
			}
		});

		this.client.on('disconnect', function() {
			console.log("Got a disconnect, clean up");
		});
	}

	Publish(message) {
    	message['node'] = this.profile;

    	var options = {
			retain: false
		};
		console.log('SENDING: ' + JSON.stringify(message));
		this.client.publish(this.topic, JSON.stringify(message), false);
	}


	// Handle all the messages that come in over the mqtt 
	// connection.
	ProcessPolyMsg(message) {
		var msg = JSON.parse(message);

		//this.log("Entered ProcessPolyMsg + " + JSON.stringify(msg));
		if (msg.node == 'polyglot') {
			if (msg.config !== undefined) {
				this.config = msg.config;

				this.log("We have a config from Polyglot");

				this.ready.emit('configured', this);

				var config = msg.config;
				this.log('ISY version: ' + config.isyVersion);
				this.log('Name       : ' + config.name);

				this.customParams = config.customParams;
				this.newParams = Object.assign({}, this.customParams);

				if (this.customParams.Units !== undefined) {
					this.log('  Using units: ' + this.customParams.Units);
				} else {
					this.newParams['Units'] = 'metric';
				}
				if (this.customParams.Elevation !== undefined) {
					this.log('  Elevation  : ' + this.customParams.Elevation);
				} else {
					this.newParams['Elevation'] = "0";
				}

				this.log('customParams = ' + JSON.stringify(this.customParams));
				this.log('newParams    = ' + JSON.stringify(this.newParams));
				//_this.log('config =');
				//_this.log(JSON.stringify(config));

				// Is there other config data that we should be 
				// looking at or saving?

			} else if (msg.connected !== undefined) {
				console.log("Polyglot says we're connected");
			} else if (msg.stop !== undefined) {
				console.log("Polyglot says stop");
			} else {
				if (msg.query !== undefined) {
				} else if (msg.command !== undefined) {
				} else if (msg.result !== undefined) {
					if (msg.result.status !== undefined) {
						if (!msg.result.status.success) {
							this.log('Error: ' + msg.result.status.reason);
						} else {
							this.log('Sucess: ' + msg.result.status.reason);
						}
					} else if (msg.result.addnode !== undefined) {
						if (!msg.result.addnode.success) {
							this.log('Error: ' + msg.result.addnode.reason);
						} else {
							this.log('Sucess: ' + msg.result.addnode.reason);
						}
					} else {
						this.log('Result: ' + JSON.stringify(msg.result));
					}
				} else if (msg.status !== undefined) {
				} else if (msg.shortPoll !== undefined) {
				} else if (msg.longPoll !== undefined) {
				} else if (msg.delete !== undefined) {
				} else {
					console.log("Polyglot something we don't understand.");
				}
			}
		} else {
			console.log("message from/for node: " + msg.node);
			//console.log(JSON.stringify(msg));
		}
	}

}

