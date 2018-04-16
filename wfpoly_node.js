//use "strict";

// Usage:
//
// var a_node = new node("asdf", "asdf", "aasdf", "myname");
// a_node.Driver = [
// 					{driver: "GV0", value: 0, uom: 56},
// 					{driver: "GV1", value: 0, uom: 36},
// 					{driver: "GV2", value: 0, uom: 14}
// 					];
//
// What is controller?  Could this just be the mqtt client?
// Seems like a lot of the items initialized in the constructor
// are really "properties" that should be exposed with getters/.
// setters.

module.exports = class WFNode {
	constructor(id, primary, address, name) {
		this.poly = null;
		this.controller = null;
		this.parent = null;
		this.primary = address;
		this.address = address;
		this.name = name;
		this.polyConfig = null;
		this.drivers = new Array();
		this.isPrimary = null;
		this.config = null;
		this.timeAdded = null;
		this.enabled = false;
		this.added = false;
		this.id = id;
		this.topic = "";
		this.profile = 0;
	}

	set Drivers(d) {
		this.drivers = d;
		//console.log("DRIVERS: " + JSON.stringify(this.drivers));
	}
	get Drivers() {
		return this.drivers;
	}

	set Poly(p) {
		this.poly = p;
	}

	set Topic(t) {
		this.topic = t;
	}

	set Profile(p) {
		this.profile = Number(p);
	}

	get NodeDef() {
		return this.id;
	}

	set NodeDef(d) {
		this.id = d;
	}

	// TODO: Only send message if value has actually changed.
	reportDriver(driver) {
		var message = {
			status: {
				address: this.address,
				driver: driver.driver,
				value: driver.value,
				uom: driver.uom
			}
		}
		//message['node'] = Number(this.profile);

		this.poly.Publish(message);
	}

	// _drivers is a dictionary <string, number>
	// or an array of object { driver: something, value: something }
	setDriver(driver, val) {
		var changed = false;

		// Look up the driver to see if anything changed
		this.drivers.forEach( function (d) {
			if (d.driver == driver) {
				if ((d.value != val.value) || (d.uom != val.uom)) {
					changed = true;
					d.value = val.value;
					d.uom = val.uom;
				}
			}
		});

		if (changed) {
			var message = {
				status: {
					address: this.address,
					driver: driver,
					value: val.value,
					uom: val.uom
				}
			}

			this.poly.Publish(message);
		}
	}


	// Send out all driver values
	reportDrivers() {
		var send = this.reportDriver;

		this.drivers.forEach( function (d) {
			send(d);
		});
	}

	updateDrivers() {
	}

	query() {
		reportDrivers();
	}

	status() {
		retportDrivers();
	}

	runCmd(command) {
	}

	// TODO what should this do?
	//      Looks like it is supposed to pull data from the config
	//      that Polyglot sends us initially.
	getDriver(dv) {
	}

	addNode() {
		// TODO: Add the node to Polyglot
		var message = {
			'addnode': {
				'nodes': [{
					'address': this.address,
					'name': this.name,
					'node_def_id': this.id,
					'primary': this.primary,
					'drivers': this.drivers
				}]
			}
		}
		//message['node'] = Number(this.profile);

		console.log ("SEND: " + JSON.stringify(message));
		this.poly.Publish(message);
	}
}

