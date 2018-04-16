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
		this.client.on('message', function(topic, message) {
			//_this.log("Received message from poly");
			if (topic == 'udi/polyglot/connections/polyglot') {
				console.log(topic + ' sent ' + message);
			} else if (topic == 'udi/polyglot/connections/' + _this.profile) {
				console.log(topic + ' sent ' + message);
			} else if (topic == _this.topic) {
				_this.ProcessPolyMsg(_this, message);
			} else {
				console.log(topic + ' unknown ' + message);
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
	ProcessPolyMsg(_this, message) {
		var msg = JSON.parse(message);

		if (msg.node == 'polyglot') {
			if (msg.config !== undefined) {
				_this.config = msg.config;

				_this.log("We have a config from Polyglot");

				_this.ready.emit('configured', _this);

				var config = msg.config;
				_this.log('ISY version: ' + config.isyVersion);
				_this.log('Name       : ' + config.name);
				if (config.customParams.Units !== undefined) {
					_this.log('Using units: ' + config.customParams.Units);
				}
				console.log('config =');
				console.log(JSON.stringify(config));

				// Build the list of known nodes (array newNodes array nodes)
				// What's the difference between the newNodes list and the
				// nodes list?  They seem the same.
				var newNodes = config.newNodes;
				var nodes = config.nodes;

				//console.log('newnodes: ' + JSON.stringify(newNodes));
				for(var i = 0; i < newNodes.length; i++) {
					// Use the configuredNodes property to get this
					//AddNode(newNodes[i]);
				}

				//console.log('nodes   : ' + JSON.stringify(nodes));
				for(var i = 0; i < nodes.length; i++) {
				}

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
							_this.log('Error: ' + msg.result.status.reason);
						} else {
							_this.log('Sucess: ' + msg.result.status.reason);
						}
					} else if (msg.result.addnode !== undefined) {
						if (!msg.result.addnode.success) {
							_this.log('Error: ' + msg.result.addnode.reason);
						} else {
							_this.log('Sucess: ' + msg.result.addnode.reason);
						}
					} else {
						_this.log('Result: ' + JSON.stringify(msg.result));
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

