# 🚢 AIS Ship Tracker for Home Assistant

This Home Assistant Add-on allows you to draw an invisible box over any body of water in the world where you wish to track shipping traffic. Whenever a ship sails into that box, the add-on will intercept its radio broadcast and instantly push the ship's name, MMSI, and the time it was spotted directly into a Home Assistant entity.

It does this by creating a sensor entity (`sensor.last_passing_ship`) that you can use to trigger notifications, sound a horn, or just keep a log of maritime traffic outside your window.

---

## 🛠️ 1. Installation

To install this Add-on, you need to add this repository to your Home Assistant Add-on Store. 

1. Open your Home Assistant dashboard and navigate to **Settings** > **Add-ons**.
2. Click the **Add-on Store** button in the bottom right corner.
3. Click the **three vertical dots** (⋮) in the top right corner and select **Repositories**.
4. Paste the URL of this GitHub repository into the box and click **Add**.
5. Close the pop-up and refresh your webpage. 
6. Scroll down to the bottom of the Add-on Store, find the **AIS Ship Tracker**, and click **Install**.

---

## 🔑 2. Getting Your API Key

This Add-on relies on [AISStream.io](https://aisstream.io), a free, community-driven network of radio receivers. To use it, you need a personal API key.

1. Go to [aisstream.io](https://aisstream.io) and sign in (you can use a GitHub or Google account).
2. Once logged in, you will be given an **API Key** (a long string of letters and numbers).
3. Copy this key. You will need to paste it into the Add-on's Configuration tab in Home Assistant.

---

## 🗺️ 3. Drawing Your Bounding Box

You need to tell the Add-on exactly where to look. We do this using a "Bounding Box" (a set of GPS coordinates that draw a rectangle on a map).

**How to get your coordinates:**
1. Go to [bboxfinder.com](http://bboxfinder.com).
2. Zoom in on the area of water you want to monitor and use the rectangle tool (the little box icon on the left) to draw your zone.
3. Look at the bottom of the screen. You will see a string of numbers that looks like this: `1.149, 50.919, 1.978, 51.229`.
   * *Note: bboxfinder gives you the numbers in this order: `Longitude 1, Latitude 1, Longitude 2, Latitude 2`.*

**How to format it for Home Assistant:**
The Add-on requires the coordinates to be grouped as `[[[Latitude 1, Longitude 1], [Latitude 2, Longitude 2]]]`. 
Notice how Latitude and Longitude swap places!

Using the example above, you would type this exactly into the Add-on Configuration box:
`[[[50.919, 1.149], [51.229, 1.978]]]`

*(Make sure you include all three sets of square brackets)*

---

## ⚠️ API Reliability

Please keep in mind that AISStream is a **free, community-supported service**. 

* **Dropped Connections:** The server may occasionally drop the connection to your Add-on if it gets too busy. The Add-on is programmed to automatically wait a few seconds and safely reconnect without you having to do anything.
* **Ghost Ships:** You will sometimes see `Unknown Ship`. This is usually because a smaller boat (like a yacht or fishing vessel) has not programmed its name into its radio transponder, or because the API hasn't caught the name yet. This is normal and is not a bug in your Add-on!

---

## 📱 Creating an Alert Automation

If you want your phone to buzz every time a ship passes, you can create a simple automation. 

**Crucial Tip:** Do not set your automation to trigger when the ship's *name* changes. If two "Unknown Ships" pass by in a row, the name doesn't change, and Home Assistant will ignore the second ship. 

Instead, trigger the automation using the **MMSI attribute**. Every ship has a mathematically unique MMSI number, so this is guaranteed to change with every single vessel.

Here is some example YAML code for an automation based on the ship's MMSI number.

```yaml
alias: "Maritime Alert: New Ship Spotted"
description: "Triggers a notification whenever a unique MMSI enters the monitoring zone."
mode: single
trigger:
  - platform: state
    entity_id: sensor.latest_passing_ship
    attribute: mmsi
condition:
  # This stops false alarms if Home Assistant reboots
  - condition: template
    value_template: "{{ trigger.to_state.state not in ['unavailable', 'unknown'] }}"
action:
  - service: notify.notify # Change this to your specific phone (e.g., notify.mobile_app_my_iphone)
    data:
      title: "🚢 Ship Spotted!"
      message: >
        Vessel Name: {{ trigger.to_state.state }}
        MMSI: {{ trigger.to_state.attributes.mmsi }}
        Time: {{ trigger.to_state.attributes.spotted_time }}

## 📱 Future Roadmap
- GPS co-ordinates in entity attributes
- Ship direction, speed and destination in entity attributes 
- Full map card support to visually track ships in bounding box
- Clear statte when ships not in bounding box
- API connectivity status entity
