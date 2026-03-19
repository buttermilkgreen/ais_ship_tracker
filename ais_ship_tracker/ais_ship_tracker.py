import json
import time
import websocket
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)

# --- Load Configuration from Home Assistant UI ---
with open('/data/options.json') as f:
    config = json.load(f)

AIS_API_KEY = config['api_key']
lat_south = float(config['latitude_south'])
lon_west = float(config['longitude_west'])
lat_north = float(config['latitude_north'])
lon_east = float(config['longitude_east'])
BOUNDING_BOX = [[[lat_south, lon_west], [lat_north, lon_east]]]
DEV_MODE = config.get('dev_mode', False)

# Home Assistant API Configuration
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
API_URL = "http://supervisor/core/api/states/sensor.last_passing_ship_dev" if DEV_MODE else "http://supervisor/core/api/states/sensor.last_passing_ship"

# Dictionary to track ships and prevent memory leaks. Format: { mmsi_number: datetime_object }
seen_ships = {}
CACHE_EXPIRY_HOURS = 24 

# Backoff variables to prevent AISStream API concurrency lockouts
RECONNECT_DELAY = 5
MAX_RECONNECT_DELAY = 120

# Map of AIS Navigational Status integers to human-readable strings
NAV_STATUS_MAP = {
    0: "Under way using engine", 1: "At anchor", 2: "Not under command",
    3: "Restricted manoeuvrability", 4: "Constrained by her draught",
    5: "Moored", 6: "Aground", 7: "Engaged in fishing",
    8: "Under way sailing", 14: "AIS-SART active", 15: "Not defined"
}

def purge_old_ships():
   # Removes ships from memory that haven't been seen recently 
    now = datetime.now()
    expired_mmsi = [
        mmsi for mmsi, last_seen in seen_ships.items() 
        if now - last_seen > timedelta(hours=CACHE_EXPIRY_HOURS)
    ]
    for mmsi in expired_mmsi:
        del seen_ships[mmsi]
    
    if expired_mmsi:
        log(f"🧹 Purged {len(expired_mmsi)} old ships from memory.")

def update_ha_entity(ship_data):
    if not SUPERVISOR_TOKEN:
        log("Error: SUPERVISOR_TOKEN not found. Are you running this inside a HA Add-on?")
        return

    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "state": ship_data["name"],
        "attributes": {
            "friendly_name": "Dev - Last Passing Ship" if DEV_MODE else "Last Passing Ship",
            "ship_name": ship_data["name"],
            "mmsi": str(ship_data["mmsi"]), 
            "spotted_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "icon": "mdi:ship-wheel",
            "latitude": ship_data["latitude"],
            "longitude": ship_data["longitude"],
            "speed_knots": ship_data["sog"],
            "course": ship_data["cog"],
            "heading": ship_data["heading"],
            "navigational_status": ship_data["nav_status_string"]
        }
    }
    
    try:
        # Convert the payload to a JSON string and encode it to bytes for urllib
        data = json.dumps(payload).encode('utf-8')
        
        req = urllib.request.Request(
            API_URL, 
            data=data, 
            headers=headers, 
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            pass 
            
    except urllib.error.URLError as e:
        log(f"Failed to update Home Assistant API: {e}")

def on_message(ws, message_json):
    try:
        message = json.loads(message_json)
        
        if message.get("MessageType") == "PositionReport":
            mmsi = message["MetaData"]["MMSI"]
            name = message["MetaData"]["ShipName"].strip() or "Unknown Ship Name"
            
            # Extract additional telemetry data from the nested 'Message' object
            pos_report = message.get("Message", {}).get("PositionReport", {})
            nav_status_int = pos_report.get("NavigationalStatus")
            
            # Build the comprehensive ship data dictionary
            ship_data = {
                "name": name,
                "mmsi": mmsi,
                "latitude": pos_report.get("Latitude"),
                "longitude": pos_report.get("Longitude"),
                "sog": pos_report.get("Sog"),
                "cog": pos_report.get("Cog"),
                "heading": pos_report.get("TrueHeading"),
                "nav_status_string": NAV_STATUS_MAP.get(nav_status_int, "Not defined")
            }
            
            # Check if this is a newly spotted ship
            if mmsi not in seen_ships:
                log(f"🚢 NEW SHIP: {name} (MMSI: {mmsi})")
                log(f"   ↳ Telemetry -> Lat: {ship_data['latitude']}, Lon: {ship_data['longitude']}, "
                    f"Speed: {ship_data['sog']}kn, Course: {ship_data['cog']}°, "
                    f"Heading: {ship_data['heading']}°, Status: {ship_data['nav_status_string']}")
                update_ha_entity(ship_data)
            
            # Always update the last seen timestamp so active ships stay in memory
            seen_ships[mmsi] = datetime.now()
            
            # Run memory cleanup periodically
            if len(seen_ships) % 100 == 0:
                purge_old_ships()
                
    except json.JSONDecodeError as e:
        log(f"JSON Decode Error: Received malformed data from AISStream - {e}")
    except KeyError as e:
        log(f"Key Error: Missing expected data key in payload - {e}")
    except Exception as e:
        # Catch-all for any other unexpected failures
        log(f"Unexpected error parsing data: {e}")

def on_error(ws, error):
    log(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    log("❌ Connection closed by server. Will attempt to reconnect...")

def on_open(ws):
    log("🟢 Connected! Monitoring the water...")
    
    subscription_message = {
        "APIKey": AIS_API_KEY,
        "BoundingBoxes": BOUNDING_BOX,
        "FilterMessageTypes": ["PositionReport"]
    }
    ws.send(json.dumps(subscription_message))

def start_tracker():
    if DEV_MODE:
        log("[DEV] [1.1.0] Connecting to AISStream. This might take up to 2 minutes...")
    else:
        log("[PROD] [1.1.0] Connecting to AISStream. This might take up to 2 minutes...")
        
    ws = websocket.WebSocketApp(
        "wss://stream.aisstream.io/v0/stream",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    ws.run_forever(ping_interval=60, ping_timeout=10)

if __name__ == "__main__":
    while True:
        start_tracker()
        log("Reconnecting in 10 seconds...")
        time.sleep(10)
