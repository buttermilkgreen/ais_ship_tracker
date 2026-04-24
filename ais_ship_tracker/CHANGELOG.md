# Changelog

## 1.3.0
* [Feature] Additional attributes added. Note these are all part of ShipStaticData and update every ~6 minutes:
  * ship_length: The total physical length of the vessel in metres
  * imo_number: The unique, permanent 7-digit identifier assigned to the hull
  * call_sign: The vessel's unique alphanumeric maritime radio call sign
  * vessel_type: The categorisation of the ship, such as "Cargo Ship", "Pleasure Craft", or "Search and Rescue".
  * destination: The intended port or location the vessel is sailing towards. Note this is manually updated by crew so may be inaccurate
  * eta: The projected arrival time at the destination, formatted as DD/MM HH:MM UTC. Note this is manually updated by crew so may be inaccurate
* [Feature] Added documentation tab to the add-on
* [Fix] Stale ships are now reliably removed in general and on restart
* [Fix] Config changes are properly applied on restart


## 1.2.1
* [Fix] Ordered bounding box fields in config to match values from bboxfinder.com for easier input

## 1.2.0
* [Feature] Ability to track multiple ships on a map card (auto-entities custom map card from HACS is recommended)
  * [Config] "Multi-Ship Tracking" - Enables this feature
  * All ships that enter the bounding box will have an entity created in the format sensor.ais_ship_{mmsi}
  * Ship entities that no longer exist in the bounding box will have the GPS co-ordinates cleared after 30 minutes of no updates (default)
  * Icons show the status of each ship. See documentation.
  * [Config] "Ship Timeout" - how long before ships that stop reporting are cleared from the map
  * [Config] "Clear Ships on Startup" - Remove all ship entities every time add on restarts 
* [Feature] Ability to track Class B vessels (smaller boats like yachts, sailing boats etc) along with attribute: vessel_class. 
  * [Config] "Enable Class B Vessels" - enables this feature
* [Feature] AISStream connectivity is now available in a new entity sensor.ais_connection_status along with attribute: error_message
* [Feature] Clearer logs to spot issues
* [Fix] Fixed an issue where the last_passing_ship entity attributes were not updated, despite getting updates from AISStream 

## 1.1.0
* [Feature] Simplified bounding box entry into the 4 co-ordinates needed. 
* [Feature] Additional attributes added to the Last Passing Ship entity:
  * latitude: The exact GPS latitude coordinate.
  * longitude: The exact GPS longitude coordinate.
  * speed_knots: The vessel's speed over ground.
  * course: The vessel's direction of travel in degrees.
  * heading: The direction the ship's bow is pointing in degrees.
  * navigational_status: A readable status of the ship (e.g., "Under way using engine").
* [Feature] Test Mode toggle which creates a separate entity called Dev - Last Passing Ship.

## 1.0.0
* Initial release