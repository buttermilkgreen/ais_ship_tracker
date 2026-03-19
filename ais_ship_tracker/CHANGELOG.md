# Changelog

## 1.1.0
* Simplified bounding box entry into the 4 co-ordinates needed. NOTE you will need to re-enter your old bounding box when updating. 
* Additional attributes added to the Last Passing Ship entity:
  * latitude: The exact GPS latitude coordinate.
  * longitude: The exact GPS longitude coordinate.
  * speed_knots: The vessel's speed over ground.
  * course: The vessel's direction of travel in degrees.
  * heading: The direction the ship's bow is pointing in degrees.
  * navigational_status: A readable status of the ship (e.g., "Under way using engine").
* Test Mode toggle which creates a separate entity called Dev - Last Passing Ship.

## 1.0.0
* Initial release
