# 🚢 AIS Ship Tracker for Home Assistant

This Home Assistant add-on allows you to draw an invisible box over any body of water in the world where you wish to track shipping traffic. Whenever a ship sails into that box, the add-on will intercept its radio broadcast and instantly push the ship's telemetry directly into a Home Assistant entity.

It creates a sensor entity (`sensor.last_passing_ship`) that you can use to trigger notifications, plot on a map, sound a horn, or just keep a log of maritime traffic outside your window.

You can also track multiple vessels and show them on a map. The [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) custom card from HACS is required for dynamically displaying these vessels. 

<img width="255" height="248" alt="SCR-20260413-mvun-2" src="https://github.com/user-attachments/assets/4df277d1-bc7f-4bc7-a8ae-e9ffec2d9622" />


---

## 🛠️ 1. Installation

To install this add-on, you need to add this repository to your Home Assistant add-on Store. 

1. Open your Home Assistant dashboard and navigate to **Settings** > **add-ons**.
2. Click the **add-on Store** button in the bottom right corner.
3. Click the **three vertical dots** (⋮) in the top right corner and select **Repositories**.
4. Paste the URL of this GitHub repository into the box and click **add**.
5. Close the pop-up and refresh the page. 
6. Scroll down to the bottom of the add-on Store, find the **AIS Ship Tracker**, and click **Install**.

---

## 🔑 2. Getting Your API Key

This add-on relies on [AISStream.io](https://aisstream.io), a free, community-driven network of radio receivers. To use it, you need a personal API key.

1. Go to [aisstream.io](https://aisstream.io) and sign in.
2. In your account, you can request an **API Key** (a long string of letters and numbers).
3. Copy this key into the add-on's Configuration tab in Home Assistant.

---

## 🗺️ 3. Drawing Your Bounding Box

You need to tell the add-on exactly where to look. To do this, imagine drawing a rectangle over a map. The add-on needs to know the exact GPS coordinates of two opposite corners: the **Bottom-Left** and the **Top-Right**. There are a number of ways you can do this but below are 2 different options. 

**How to find your coordinates using bboxfinder:**
1. Go to [bboxfinder.com](http://bboxfinder.com).
2. Zoom in on the area of water you want to monitor.
3. Click the **rectangle tool** (the small box icon on the left of the map) and draw your tracking zone.
4. Look at the very bottom of the screen. You will see a string of four numbers next to the word **Box** (e.g., `-2.718, 51.423, -2.521, 51.501`).
5. **CRITICAL STEP:** bboxfinder outputs these numbers in a specific order: `Longitude, Latitude, Longitude, Latitude`. You must paste them into your add-on configuration in exactly this mapping:
   * **First number:** Paste into `longitude_west`
   * **Second number:** Paste into `latitude_south`
   * **Third number:** Paste into `longitude_east`
   * **Fourth number:** Paste into `latitude_north`

---
## 📍 4. Multi-Ship Tracking (Map Card)
You can track multiple ships simultaneously for viewing on a map. The [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) custom card from HACS is required for dynamically displaying these vessels. [Card-mod](https://github.com/thomasloven/lovelace-card-mod) is also recommended to make the ship icons smaller using CSS.

When the *"Multi-Ship Tracking"* configuration is enabled:
* Every ship that enters your bounding box will automatically generate a dedicated entity formatted as sensor.ais_ship_{mmsi}.
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

**Class B Vessels:**
You can also choose to track smaller leisure craft (yachts, sailing boats, etc.) by enabling "Enable Class B Vessels" in the configuration.
___

## 📊 Entity Attributes & Telemetry

The add-on creates and updates a single entity: `sensor.last_passing_ship`. The main state of this sensor will always be the name of the most recently spotted ship. 

Attached to this entity is a set of attributes extracted directly from the vessel's radio transponder:

* **`mmsi`**: The Maritime Mobile Service Identity. This is a unique 9-digit number assigned to the vessel.
* **`spotted_time`**: The exact local time the transponder data was received.
* **`latitude`**: The exact GPS latitude coordinate.
* **`longitude`**: The exact GPS longitude coordinate.
* **`speed_knots`**: The vessel's current speed over ground.
* **`course`**: The vessel's direction of travel in degrees.
* **`heading`**: The true direction the ship's bow is pointing in degrees.
* **`navigational_status`**: The current operational state of the vessel (e.g., "Under way using engine", "At anchor", "Moored").

*The entity is compatible with the HA map card, but until a future release, you will only see 1 ship at a time*

---

## ⚠️ API Reliability

Please keep in mind that AISStream is a **free, community-supported service**. 

* **Dropped Connections:** The server may occasionally drop the connection to your add-on if it gets too busy. The add-on will try to reconnect without you having to do anything. Look in the add-on logs if you suspect constant connectivity issues.
* **Ghost Ships:** You may sometimes see `Unknown Ship Name`. This usually happens because a smaller boat (like a yacht or fishing vessel) has not programmed its name into its radio transponder, or because the API simply hasn't caught the broadcasted name yet. This is normal behaviour.
* **Outages:** Sometimes the add-on appears to be connected in the logs, but no ships are being reported. You can sometimes check for ongoing API service issues here (it isnt a live status page and relies on users reporting issues): [AISStream Issues](https://github.com/aisstream/issues/issues).

---

## 📱 Creating an Alert Automation

**Crucial Tip:** Do not set your automation to trigger when the ship's *name* changes. If two "Unknown Ship Name" vessels pass by in a row, the state doesn't change, and Home Assistant will ignore the second ship. 

Instead, trigger the automation using the **`mmsi`** attribute. Every ship has a unique MMSI number, so this is guaranteed to change with every single vessel.

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

---

## 🎚️ Test Mode 

TBH this mainly helps with development and can be ignored...but in the interest of good documentation:

When you switch this on and restart the add-on, the main sensor will stop updating and instead a separate entity called `sensor.last_passing_ship_dev` will appear and start updating. The logs will indicate if you are in test mode by prepending `[DEV]` to the initial log line. 

---
## 🐛 Issues or feedback?

Please use [this form](https://forms.gle/KQDVQQpGf2LZofWA8) or raise a Github issue.  
