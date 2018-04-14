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
function GotInput(Poly) {
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
	var udp = new WFUDP();
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

function doAir(j) {
	console.log('In the air observation handler');
	var inhg = (Number(j.obs[0][1]) * 0.02952998751).toFixed(3);
	log('inHg = ' + j.obs[0][1] + 'mb -> ' + inhg.toString());
	if (nodelist[j.serial_number] === undefined) {
		//logStream.write('serial number ' + j.serial_number + ' not found');
		log('serial number ' + j.serial_number + ' not found');
		nodelist[j.serial_number] = new WFNode("WF_Air", "",
											   sn_2_address(j.serial_number),
											   j.serial_number);
		nodelist[j.serial_number].Poly = Poly;
		//nodelist[j.serial_number].Topic = topicInput;
		//nodelist[j.serial_number].Profile = profileNum;
		nodelist[j.serial_number].Drivers = [
			{driver: "GV0", value: 0, uom: 25}, // Last update
			{driver: "GV1", value: j.obs[0][2], uom: 4}, // temp
			{driver: "GV2", value: j.obs[0][3], uom: 22}, // humidity
			{driver: "GV3", value: inhg, uom: 23}, // pressure
			{driver: "GV4", value: j.obs[0][4], uom: 25}, // strikes
			{driver: "GV5", value: j.obs[0][5], uom: 83}, // distance
			{driver: "GV6", value: 0, uom: 4}, // dew
			{driver: "GV7", value: 0, uom: 4}, // apparent
			{driver: "GV8", value: 1, uom: 25}, // trend
			{driver: "GV9", value: j.obs[0][6], uom: 72}, // battery
		];

		log('Adding node for serial number ' + j.serial_number);
		nodelist[j.serial_number].addNode();
	} else {
		// Update node drivers with j.obs[0][xxx] values
		nodelist[j.serial_number].setDriver("GV1", j.obs[0][2]);
		nodelist[j.serial_number].setDriver("GV2", j.obs[0][3]);
		nodelist[j.serial_number].setDriver("GV3", inhg);
		nodelist[j.serial_number].setDriver("GV4", j.obs[0][4]);
		nodelist[j.serial_number].setDriver("GV5", j.obs[0][5]);
		nodelist[j.serial_number].setDriver("GV9", j.obs[0][6]);
		//TODO: Figure out how to get calculated values
		//      that rely on other node data
	}
}

function doSky(j) {
	console.log('In the sky observation handler');
	var windSpeed = (Number(j.obs[0][5]) * (18 / 5)).toFixed(2);
	var gustSpeed = (Number(j.obs[0][6]) * (18 / 5)).toFixed(2);
	var lullSpeed = (Number(j.obs[0][4]) * (18 / 5)).toFixed(2);
	if (nodelist[j.serial_number] === undefined) {
		//logStream.write('serial number ' + j.serial_number + ' not found');
		log('serial number ' + j.serial_number + ' not found');
		nodelist[j.serial_number] = new WFNode("WF_Sky", "",
											   sn_2_address(j.serial_number),
											   j.serial_number);
		nodelist[j.serial_number].Poly = Poly;
		//nodelist[j.serial_number].Topic = topicInput;
		//nodelist[j.serial_number].Profile = profileNum;
		nodelist[j.serial_number].Drivers = [
			{driver: "GV0", value: 0, uom: 25}, // Last update
			{driver: "GV1", value: j.obs[0][1], uom: 36}, // lux
			{driver: "GV2", value: j.obs[0][2], uom: 71}, // uv
			{driver: "GV3", value: j.obs[0][10], uom: 74}, // radiation
			{driver: "GV4", value: windSpeed, uom: 32}, // kph speed
			{driver: "GV5", value: gustSpeed, uom: 32}, // kph gust
			{driver: "GV6", value: lullSpeed, uom: 32}, // kph lull
			{driver: "GV7", value: j.obs[0][7], uom: 14}, // direction
			{driver: "GV8", value: 0, uom: 46}, // rain rate in/mm
			{driver: "GV9", value: 0, uom: 82}, // daily rain
			{driver: "GV10", value: j.obs[0][8], uom: 72}, // battery
			{driver: "GV11", value: j.obs[0][12], uom: 25} // rain type
		];

		log('Adding node for serial number ' + j.serial_number);
		nodelist[j.serial_number].addNode();
	} else {
		// Update node drivers with j.obs[0][xxx] values
		nodelist[j.serial_number].setDriver("GV1", j.obs[0][1]);
		nodelist[j.serial_number].setDriver("GV2", j.obs[0][2]);
		nodelist[j.serial_number].setDriver("GV3", j.obs[0][10]);
		nodelist[j.serial_number].setDriver("GV4", windSpeed);
		nodelist[j.serial_number].setDriver("GV5", gustSpeed);
		nodelist[j.serial_number].setDriver("GV6", lullSpeed);
		nodelist[j.serial_number].setDriver("GV7", j.obs[0][7]);
		nodelist[j.serial_number].setDriver("GV10", j.obs[0][8]);
		nodelist[j.serial_number].setDriver("GV11", j.obs[0][12]);
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

