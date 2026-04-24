# 🚢 AIS Ship Tracker for Home Assistant

This Home Assistant add-on allows you to draw an invisible box over any body of water in the world where you wish to track shipping traffic. Whenever a ship sails into that box, the add-on will intercept its radio broadcast and instantly push the ship's telemetry directly into a Home Assistant entity.

It creates a sensor entity (`sensor.last_passing_ship`) that you can use to trigger notifications, plot on a map, sound a horn, or just keep a log of maritime traffic outside your window.

You can also track multiple vessels and show them on a map. The [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) custom card from HACS is required for dynamically displaying these vessels. 

**Dashboard Example**

<img width="640" height="441" alt="Dashboard Example" src="https://github.com/user-attachments/assets/1a4e671f-60b4-4144-b426-e8ffdf0148a9" />

---

**More Info - Attributes** 

<img width="196" height="320" alt="More Info Attributes" src="https://github.com/user-attachments/assets/90077aad-f351-4145-8c90-4f2bdc167eb4" />


---

## 🛠️ Installation

To install this add-on, you need to add this repository to your Home Assistant add-on Store. 

1. Open your Home Assistant dashboard and navigate to **Settings** > **add-ons**.
2. Click the **add-on Store** button in the bottom right corner.
3. Click the **three vertical dots** (⋮) in the top right corner and select **Repositories**.
4. Paste the URL of this GitHub repository into the box and click **add**.
5. Close the pop-up and refresh the page. 
6. Scroll down to the bottom of the add-on Store, find the **AIS Ship Tracker**, and click **Install**.
7. Enter you API key and bounding box co-ordinates. Steps in section #2 and #3

*Optional steps for showing multiple ships on a map*

8. Install [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) to allow you to have a map card with multiple ship entities 
9. Install [Card-mod](https://github.com/thomasloven/lovelace-card-mod) to allow you to make the ship icons on the map smaller
10. Section #4 has the yaml to configure a multi-ship map.

---

## 🔑 Getting Your API Key

This add-on relies on [AISStream.io](https://aisstream.io), a free, community-driven network of radio receivers. To use it, you need a personal API key.

1. Go to [aisstream.io](https://aisstream.io) and sign in.
2. In your account, you can request an **API Key** (a long string of letters and numbers).
3. Copy this key into the add-on's Configuration tab in Home Assistant.

---

## 🗺️ Drawing Your Bounding Box

You need to tell the add-on exactly where to look. To do this, imagine drawing a rectangle over a map. The add-on needs to know the exact GPS coordinates of two opposite corners: the **Bottom-Left** and the **Top-Right**. The easiest way to do this is with BBoxFinder. 

**How to find your coordinates using bboxfinder:**
1. Go to [bboxfinder.com](http://bboxfinder.com).
2. Zoom in on the area of water you want to monitor.
3. Click the **rectangle tool** (the small box icon on the left of the map) and draw your tracking zone.
4. Look at the very bottom of the screen. You will see a string of four numbers next to the word **Box** (e.g., `-2.718, 51.423, -2.521, 51.501`).
5. Paste the numbers into the boxes in order in the add-on config:
   * **First number:** Paste into `Bottom-Left Longitude (West)`
   * **Second number:** Paste into `Bottom-Left Latitude (South)`
   * **Third number:** Paste into `Top-Right Longitude (East)`
   * **Fourth number:** Paste into `Top-Right Latitude (North)`

---
## 📍 Multi-Ship Tracking (Map Card)
You can track multiple ships simultaneously for viewing on a map. The [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) custom card from HACS is required for dynamically displaying these vessels. The official HA Map card will not populate dynamically. Given this add on creates entities for ships as they enter our bounding box, it needs this alternative map solution.  
[Card-mod](https://github.com/thomasloven/lovelace-card-mod) is also recommended to make the ship icons smaller using CSS.

When the *"Multi-Ship Tracking"* configuration is enabled:
* Every ship that enters your bounding box will automatically generate a dedicated entity formatted as `sensor.ais_ship_{mmsi}`.
* These entities dynamically update their GPS co-ordinates and include an icon indicating their current navigational status.
* Ship Timeout: To keep your map clean, ships that stop broadcasting will have their co-ordinates cleared after a specified period of inactivity (default is 30 minutes, configurable via "Ship Timeout").
* Clear Ships on Startup: You can configure the add-on to automatically purge all existing ship entities from the map whenever the add-on is restarted.

Example YAML for a solid map view using auto-entities and card-mod:
```yaml
type: custom:auto-entities
show_empty: false
card:
  type: map
  title: null
  dark_mode: false
  cluster: false
  card_mod:
    style:
      ha-map $ ha-entity-marker $: |
        .marker {
          height: 30px !important;
          width: 30px !important;
        }
filter:
  include:
    - entity_id: sensor.ais_ship_*
      options:
        label_mode: icon
```

<img width="255" height="248" alt="Map View" src="https://github.com/user-attachments/assets/4df277d1-bc7f-4bc7-a8ae-e9ffec2d9622" />

### Icon Reference

The ship's icon on the map is based on its current navigational status. This status is also available as an attribute. If a status is not defined by the vessel, it defaults to a standard ferry icon.

| Icon | Navigational Status | MDI Name |
| :---: | :--- | :--- |
| <img src="https://api.iconify.design/mdi/ferry.svg" width="20"> | Under way using engine | `mdi:ferry` |
| <img src="https://api.iconify.design/mdi/anchor.svg" width="20"> | At anchor | `mdi:anchor` |
| <img src="https://api.iconify.design/mdi/pier.svg" width="20"> | Moored | `mdi:pier` |
| <img src="https://api.iconify.design/mdi/fish.svg" width="20"> | Engaged in fishing | `mdi:fish` |
| <img src="https://api.iconify.design/mdi/sail-boat.svg" width="20"> | Under way sailing | `mdi:sail-boat` |
| <img src="https://api.iconify.design/mdi/lifebuoy.svg" width="20"> | Aground | `mdi:lifebuoy` |
| <img src="https://api.iconify.design/mdi/lifebuoy.svg" width="20"> | Not under command | `mdi:lifebuoy` |
| <img src="https://api.iconify.design/mdi/lifebuoy.svg" width="20"> | Restricted manoeuvrability | `mdi:lifebuoy` |
| <img src="https://api.iconify.design/mdi/lifebuoy.svg" width="20"> | Constrained by her draught | `mdi:lifebuoy` |
| <img src="https://api.iconify.design/mdi/lifebuoy.svg" width="20"> | AIS-SART active | `mdi:lifebuoy` |
| <img src="https://api.iconify.design/mdi/ferry.svg" width="20"> | Not defined / Unknown | `mdi:ferry` |

___

## 📊 Entity Attributes & Telemetry

The add-on creates and updates a single entity by default: `sensor.last_passing_ship`. The main state of this sensor will always be the name of the most recently spotted ship. 

Attached to this entity is a set of attributes extracted directly from the vessel's radio transponder. Where you enable `Multi-ship Tracking`, all ship entities are created with the attributes below. 

The following update every ~10 seconds for ships underway and ~3 minutes for ships at anchor/moored
* **`mmsi`**: The Maritime Mobile Service Identity. This is a unique 9-digit number assigned to the vessel.
* **`spotted_time`**: The exact local time the transponder data was received.
* **`latitude`**: The exact GPS latitude coordinate.
* **`longitude`**: The exact GPS longitude coordinate.
* **`speed_knots`**: The vessel's current speed over ground.
* **`course`**: The vessel's direction of travel in degrees.
* **`heading`**: The true direction the ship's bow is pointing in degrees.
* **`navigational_status`**: The current operational state of the vessel (e.g., "Under way using engine", "At anchor", "Moored").
* **`vessel_class`**: The class of the current vessel, either Class A (generally for commercial vessels) or Class B (generally for leisure vessels).

The following update every ~6 minutes for ships underway and at anchor/moored:

* **`ship_length`**: The total physical length of the vessel in metres.
* **`imo_number`**: The unique, permanent 7-digit identifier assigned to the hull.
* **`call_sign`**: The vessel's unique alphanumeric maritime radio call sign.
* **`vessel_type`**: The categorisation of the ship, such as "Cargo Ship", "Pleasure Craft", or "Search and Rescue".
* **`destination`**: The intended port or location the vessel is sailing towards. Note this is manually updated by crew so can vary in quality and accuracy. 
* **`eta`**: The projected arrival time at the destination, formatted as DD/MM HH:MM UTC. Note this is manually updated by crew so can vary in quality and accuracy. 



**Example of how this appears:**

```yaml
state:
  translated: "11.9"
  raw: "11.9"
  last_changed: "2026-04-23T15:06:23.721Z"
  last_updated: "2026-04-23T15:06:23.721Z"
attributes:
  friendly_name: GOLDEN CALYPSO
  ship_name: GOLDEN CALYPSO
  mmsi: "352006081"
  spotted_time: "2026-04-23 16:06:23"
  latitude: 51.00354
  longitude: 1.4393983333333333
  speed_knots: 11.9
  course: 227.8
  heading: 227
  navigational_status: Under way using engine
  vessel_class: Class A
  icon: mdi:ferry
  destination: GBFAW
  eta: 24/04 01:00 UTC
  ship_length: 156
  imo_number: "1037713"
  call_sign: "3E8544"
  vessel_type: Tanker
```

**Note:** When `Multi-ship Tracking` is enabled, entities are created for every ship that enters the bounding box. After the `Ship Entity Timeout` expires (default 30 minutes), ships will be removed from the map **but** they will remain in your Home Assistant entity list until the next Home Assistant restart. This is due to how the Home Assistant REST API works, in that you can only create and modify entities, but not delete them. 

---
## 🛠️ Config Specifics

* **`API Key`**: The free API key you need to generate from [AISStream.io](https://aisstream.io).
* **`Bounding Box - Bottom-Left Longitude (West)`**: Left edge of the bounding box and the first number from bboxfinder co-ordinates.
* **`Bounding Box - Bottom-Left Latitude (South)`**: Bottom edge of the bounding box and the second number from bboxfinder co-ordinates.
* **`Bounding Box - Top-Right Longitude (East)`**: Right edge of the bounding box and the third number from bboxfinder co-ordinates.
* **`Bounding Box - Top-Right Latitude (North)`**: Top edge of the bounding box and the fourth number from bboxfinder co-ordinates.
* **`Include Class B Vessels`**: Class B vessels (typically leisure craft) will be shown
* **`Multi-Ship Tracking`**: Creates new entities for all ships that enter the bounding box in the format `sensor.ais_ship_{mmsi}`
* **`Ship Entity Timeout (Minutes)`**: How long before ships are cleared from the map after receiving no updates.
* **`Clear Ship Entities on Startup`**: Clears all ship entities from the map when add-on starts.
* **`Test Mode`**: The main sensors will stop updating and all sensors will be appended with `_dev`. For example `sensor.last_passing_ship_dev`, `sensor.ais_connection_status_dev`, `sensor.ais_ship_{mmsi}_dev`


---

## ⚠️ API Reliability

Please keep in mind that AISStream is a **free, community-supported service**. 

* **Dropped Connections:** The server may occasionally drop the connection to your add-on if it gets too busy. The add-on will try to reconnect without you having to do anything. Look in the add-on logs if you suspect constant connectivity issues.
* **Ghost Ships:** You may sometimes see `Unknown Ship Name`. This usually happens because a smaller boat (like a yacht or fishing vessel) has not programmed its name into its radio transponder, or because the API simply hasn't caught the broadcasted name yet. This is normal behaviour.
* **Outages:** Sometimes the add-on appears to be connected in the logs, but no ships are being reported. You can sometimes check for ongoing API service issues here (it isnt a live status page and relies on users reporting issues): [AISStream Issues](https://github.com/aisstream/issues/issues).

The add-on does show connectivity state via entity `sensor.ais_connection_status` and if in doubt, check the logs. 


---

## 📱 Creating an Alert Automation


The best approach for triggering an automation when new ships enter the bounding box is to use the **`mmsi`** attribute. Every ship has a unique MMSI number, so this is guaranteed to change with every single vessel.

Here is an example YAML automation that utilises the telemetry data. Replace the `notify.notify` action with your preferred notification service. 

```yaml
alias: Ship Alerts
description: Triggers a notification whenever a unique MMSI enters the tracking zone.
triggers:
  - entity_id:
      - sensor.last_passing_ship
    trigger: state
    attribute: mmsi # <--- Only fires when the unique MMSI changes
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.state not in ['unavailable', 'unknown'] }}"
actions:
  - data:
      title: 🚢 Ship Spotted: {{ trigger.to_state.state }}
      message: >
        MMSI: {{ trigger.to_state.attributes.mmsi }}
        Speed: {{ trigger.to_state.attributes.speed_knots }} knots
        Status: {{ trigger.to_state.attributes.navigational_status }}
        Time: {{ trigger.to_state.attributes.spotted_time }}
    action: notify.notify 
mode: single
```

**Tip:** Do not set your automation to trigger when the ship's *name* changes. If two "Unknown Ship Name" vessels pass by in a row, the state doesn't change, and Home Assistant will ignore the second ship. 


---
## 🐛 Issues or feedback?

Please raise a Github issue.  
