#!/usr/bin/env node
const mqtt = require('mqtt');
const os= require('os');
const fs = require('fs-extra');
const events = require('events');
const url = require('url');
var WFUDP = require('./wfpoly_udp.js');
var WFNode = require('./wfpoly_node.js');
var PolyMQTT = require('./wfpoly_mqtt.js');


// Set up logging
const file = './logs/debug.log';
const logopts = {flag: 'a'};
async function log(text) {
	await fs.outputFile(file, `${text}${os.EOL}`, logopts);
}

// How do we really get our profile number?
// From the example, it seems we need to check for an ENVIRONMENT
// variable or from stdin. That seems crazy.
//  maybe on stdin {"token":"asdasdf", "mqttHost":"localhost",
//  "mqttPort":"1883","profileNum":"xx"}
// Or check env PROFILE_NUM?
var profileNum = "3";
var units = 'metric';
var nodelist = {};
var mqttHost = 'mqtts://192.168.92.100';
var mqttPort = 1883;
var em = new events.EventEmitter();
var Poly;


process.stdin.setEncoding('utf-8');
var data = '';
var profile_number = 0;
process.stdin.on('readable', function() {
	var chunk;
	console.log("Waiting for stdin....");
	log("Waiting for stdin....");
	while(chunk = process.stdin.read()) {
		data += chunk;
		log(data);
	}

	// Can we assume that we have some data at this point?
	if (data != '') {
		polyinput = JSON.parse(data);
		log('Profile = ' + polyinput.profileNum);
		profileNum = polyinput.profileNum;
		mqttHost = 'mqtts://' + polyinput.mqttHost;
        mqttPort = Number(polyinput.mqttPort);

		// Send an event to indicate that we can really start
		em.emit('Ready', Poly);
	}

});

process.stdin.on('end', function() {
	data = data.replace(/\n$/, '');
	log('in END - ' + data);
	profile_number = Number(data);
});

//
// Starting node server
// 

// Wait here until we have the info needed to start
console.log('Starting');
log('Starting WeatherFlowPoly');
log('ProfileNumberEnv: ' + process.env.PROFILE_NUM);
log('ProfileNumberStdin: ' + profile_number);
log('stdin: ' + data);

_this = this;
em.on('Ready', GotInput);
function GotInput(aPoly) {
	console.log('We now have all our input, start mqtt here??');
	log('We now have all our input, start mqtt here??');

	// Start mqtt connection with Polyglot
	Poly = new PolyMQTT(mqttHost, mqttPort, profileNum, em, log);
	Poly.Start();
	log('MQTT connection with Polyglot has been started.');
}

// Wait for mqtt connection to stabilize
//em.on('configured', Configure(log));

em.on('configured', function(Poly) {
	console.log("MQTT connection has been configured");
	log("MQTT connection has been configured");
	// Get nodes from Poly
	var nodes = Poly.ConfiguredNodes;

	for(var i = 0; i < nodes.length; i++) {
		AddNode(nodes[i], Poly);
	}

	// Start UDP listener for WeatherFlow data
	var udp = new WFUDP(log);
	udp.Air = doAir;
	udp.Sky = doSky;
	udp.Start();
});


///////////////////////////////////////////////////////////////////////////


function AddNode(node, Poly) {
	var sn = node.name;

	log('Adding:  ' + node.name + '(' + node.address + ')');
	nodelist[sn] = new WFNode(node.nodedef, "",
							  sn_2_address(sn), node.name);

	if (Poly === undefined)
		log('AddNode error: Poly is undefined.');

	nodelist[sn].Poly = Poly;
	//nodelist[sn].Topic = topicInput;
	//nodelist[sn].Profile = profileNum;

	var drvs = new Array();
	for (var key in node.drivers) {
		if (node.drivers.hasOwnProperty(key)) {
			drvs.push( { driver: key,
					  value: node.drivers[key].value,
					  uom: node.drivers[key].uom } );

		}
	}
	nodelist[sn].Drivers = drvs;
}

// convert the data values from metric to imperial
function toImperial(data) {
}

function doAir(j) {
	console.log('In the air observation handler');
	if (Poly.Units != 'metric')
		j = toImperial(j);

	if (nodelist[j.serial_number] === undefined) {
		log('serial number ' + j.serial_number + ' not found');
		nodelist[j.serial_number] = new WFNode("WF_Air", "",
											   sn_2_address(j.serial_number),
											   j.serial_number);
		nodelist[j.serial_number].Poly = Poly;
		nodelist[j.serial_number].Drivers = [
			{driver: "GV0", value: 0, uom: 25}, // Last update
			{driver: "GV1", value: j.temperature.value, uom: j.temperature.uom},
			{driver: "GV2", value: j.humidity.value, uom: j.humidity.uom},
			{driver: "GV3", value: j.sealevel.value, uom: j.sealevel.uom},
			{driver: "GV4", value: j.strikes.value, uom: j.strikes.uom},
			{driver: "GV5", value: j.strike_distance.value, uom: j.strike_distance.uom},
			{driver: "GV6", value: j.dewpoint.value, uom: j.dewpoint.uom},
			{driver: "GV7", value: j.apparent_temp.value, uom: j.apparent_temp.uom},
			{driver: "GV8", value: j.trend.value, uom: j.trend.uom},
			{driver: "GV9", value: j.battery.value, uom: j.battery.uom},
		];

		log('Adding node for serial number ' + j.serial_number);
		nodelist[j.serial_number].addNode();
	} else {
		log('GV6 = ' + j.dewpoint.value);
		log('GV7 = ' + j.apparent_temp.value);
		// Update node drivers 
		nodelist[j.serial_number].setDriver("GV1", j.temperature.value);
		nodelist[j.serial_number].setDriver("GV2", j.humidity.value);
		nodelist[j.serial_number].setDriver("GV3", j.sealevel.value);
		nodelist[j.serial_number].setDriver("GV4", j.strikes.value);
		nodelist[j.serial_number].setDriver("GV5", j.strike_distance.value);
		nodelist[j.serial_number].setDriver("GV6", j.dewpoint.value);
		nodelist[j.serial_number].setDriver("GV7", j.apparent_temp.value);
		nodelist[j.serial_number].setDriver("GV8", j.trend.value);
		nodelist[j.serial_number].setDriver("GV9", j.battery.value);
	}
}

function doSky(j) {
	console.log('In the sky observation handler');
	if (nodelist[j.serial_number] === undefined) {
		log('serial number ' + j.serial_number + ' not found');
		nodelist[j.serial_number] = new WFNode("WF_Sky", "",
											   sn_2_address(j.serial_number),
											   j.serial_number);
		nodelist[j.serial_number].Poly = Poly;
		nodelist[j.serial_number].Drivers = [
			{driver: "GV0", value: 0, uom: 25}, // Last update
			{driver: "GV1", value: j.illuminance.value, uom: j.illuminance.uom},
			{driver: "GV2", value: j.uv.value, uom: j.uv.uom},
			{driver: "GV3", value: j.solar_radiation.value, uom: j.solar_radiation.uom},
			{driver: "GV4", value: j.wind_speed.value, uom: j.wind_speed.uom},
			{driver: "GV5", value: j.gust_speed.value, uom: j.gust_speed.uom},
			{driver: "GV6", value: j.lull_speed.value, uom: j.lull_speed.uom},
			{driver: "GV7", value: j.wind_direction.value, uom: j.wind_direction.uom},
			{driver: "GV8", value: j.rain_rate.value, uom: j.rain_rate.uom},
			{driver: "GV9", value: j.rain_daily.value, uom: j.rain_daily.uom},
			{driver: "GV10", value: j.battery.value, uom: j.battery.uom},
			{driver: "GV11", value: j.rain_type.value, uom: j.rain_type.uom}
		];

		log('Adding node for serial number ' + j.serial_number);
		nodelist[j.serial_number].addNode();
	} else {
		// Update node drivers
		nodelist[j.serial_number].setDriver("GV1", j.illuminance.value);
		nodelist[j.serial_number].setDriver("GV2", j.uv.value);
		nodelist[j.serial_number].setDriver("GV3", j.solar_radiation.value);
		nodelist[j.serial_number].setDriver("GV4", j.wind_speed.value);
		nodelist[j.serial_number].setDriver("GV5", j.gust_speed.value);
		nodelist[j.serial_number].setDriver("GV6", j.lull_speed.value);
		nodelist[j.serial_number].setDriver("GV7", j.wind_direction.value);
		nodelist[j.serial_number].setDriver("GV8", j.rain_rate.value);
		nodelist[j.serial_number].setDriver("GV9", j.rain_daily.value);
		nodelist[j.serial_number].setDriver("GV10", j.battery.value);
		nodelist[j.serial_number].setDriver("GV11", j.rain_type.value);
	}
}

function sn_2_address(sn) {
	var snstr = String(sn);
	snstr = snstr.split('-').join('_');
	var addr = snstr.toLowerCase();

	return addr;
}

// What are the types of messages we can publish
//  and on which topic?

// Add a node to the NodeServer (and to the ISY?)
//var message = {
//	'addnode': {
//		'nodes': [{
//			'address': '<node address>',
//			'name': '<node name>',
//			'node_def_id': '<id>',
//			'primary': 'true | false or address?',
//			'drivers': '???  another json formatted object?'
//		}]
//	}
//};

// data is key/value pairs to store in pPolygot database
//var message = { 'customdata': data };

// data is key/value pairs to store in pPolygot database
//var message = { 'customparams': data };

// custom notice to front-end for this Node Server
//var message = { 'addnotice': string };
//var message = { 'removenotice': string };

// Ask Polyglot to restart me
//var message = { 'restart' : {} };

// Install profile files on ISY
//var message = { 'installprofile': { 'reboot': False } };

// Delete a node from the Node Server
//var message = { 'removenode': { 'address': '<address>' } };

