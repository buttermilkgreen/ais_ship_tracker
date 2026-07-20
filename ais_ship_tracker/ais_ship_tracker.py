import json
import time
import websocket
import random
import os

# Set default socket timeout for websocket-client handshake to prevent hanging connections
websocket.setdefaulttimeout(15)
import urllib.request
import urllib.error
import signal
import sys
import threading
from datetime import datetime, timedelta

print("🚀 Starting AIS Ship Tracker...", flush=True)
VERSION = "1.4.6"

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        print(f"[{timestamp}] {message}", flush=True)
    except UnicodeEncodeError:
        # Fallback for Docker environments that don't support UTF-8 emojis
        print(f"[{timestamp}] {message.encode('ascii', 'ignore').decode('ascii')}", flush=True)

watchlist_mmsis = []

try:
    # --- Load Configuration from Home Assistant UI ---
    with open('/data/options.json') as f:
        config = json.load(f)

    def get_safe_int(key, default):
        val = config.get(key)
        if val is None or val == "": return default
        try: return int(val)
        except: return default

    AIS_API_KEY = config.get('api_key', '')
    lat_south = float(config.get('latitude_south', 50.90))
    lon_west = float(config.get('longitude_west', 1.20))
    lat_north = float(config.get('latitude_north', 51.20))
    lon_east = float(config.get('longitude_east', 1.80))
    BOUNDING_BOX = [[[lat_south, lon_west], [lat_north, lon_east]]]
    
    dev_val = config.get('dev_mode', False)
    DEV_MODE = str(dev_val).lower() in ['true', '1', 't', 'y', 'yes'] if dev_val is not None else False

    # Version 1.2.0 Additions
    map_val = config.get('enable_map_entities', False)
    ENABLE_MAP_ENTITIES = str(map_val).lower() in ['true', '1', 't', 'y', 'yes'] if map_val is not None else False
    
    MAP_TIMEOUT_MINUTES = get_safe_int('map_timeout_minutes', 30)
    
    clear_val = config.get('clear_map_on_startup', False)
    CLEAR_MAP_ON_STARTUP = str(clear_val).lower() in ['true', '1', 't', 'y', 'yes'] if clear_val is not None else False
    
    class_b_val = config.get('include_class_b', True)
    INCLUDE_CLASS_B = str(class_b_val).lower() in ['true', '1', 't', 'y', 'yes'] if class_b_val is not None else True

    # Version 1.5.0 Additions - API Uptime Monitoring
    api_monitor_val = config.get('enable_api_monitoring', True)
    ENABLE_API_MONITORING = str(api_monitor_val).lower() in ['true', '1', 't', 'y', 'yes'] if api_monitor_val is not None else True
    default_monitor_url = 'http://192.168.4.138/api/v1/status?simple=true' if DEV_MODE else 'https://aisuptime.buttermilkgreen.fyi/api/v1/status?simple=true'
    API_MONITORING_URL = config.get('api_monitoring_url', default_monitor_url)
    API_MONITORING_INTERVAL = get_safe_int('api_monitoring_interval', 60)
    # Clamp interval to minimum 10 seconds to avoid spamming the endpoint
    if API_MONITORING_INTERVAL < 10:
        API_MONITORING_INTERVAL = 10

    WEBSOCKET_URL = "wss://stream.aisstream.io/v0/stream"
    if DEV_MODE:
        custom_ws_url = config.get('websocket_url', '')
        if custom_ws_url:
            WEBSOCKET_URL = custom_ws_url

    vessel_watchlist_raw = config.get('vessel_watchlist', '')
    if vessel_watchlist_raw:
        for item in vessel_watchlist_raw.split(','):
            if not item.strip():
                continue
            # Sanitisation: strip all whitespace
            cleaned = "".join(item.split())
            # Remove any non-numeric characters
            numeric_only = "".join(c for c in cleaned if c.isdigit())
            # Validation
            if len(numeric_only) == 9:
                watchlist_mmsis.append(numeric_only)
            else:
                log(f"⚠️ Invalid MMSIs in filter box ignored: '{item.strip()}' (Must be 9 digits)")

except Exception as e:
    print(f"❌ FATAL ERROR loading configuration: {e}", flush=True)
    import sys
    sys.exit(1)

import uuid
# --- Load or Generate Persistent UUID ---
UUID_FILE_PATH = "/data/tracker_uuid.txt"
LOCAL_UUID_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker_uuid.txt")
try:
    env_uuid = os.environ.get("TRACKER_UUID")
    if env_uuid and env_uuid.strip():
        TRACKER_UUID = env_uuid.strip()
    elif os.path.exists(LOCAL_UUID_FILE_PATH):
        with open(LOCAL_UUID_FILE_PATH, "r", encoding="utf-8") as f:
            TRACKER_UUID = f.read().strip()
        if not TRACKER_UUID:
            raise ValueError("Local UUID file is empty")
    elif os.path.exists(UUID_FILE_PATH):
        with open(UUID_FILE_PATH, "r", encoding="utf-8") as f:
            TRACKER_UUID = f.read().strip()
    else:
        TRACKER_UUID = str(uuid.uuid4())
        with open(UUID_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(TRACKER_UUID)
    log(f"Tracker UUID initialized: {TRACKER_UUID[:8]}...")
except Exception as e:
    # Fallback to a temporary UUID if file system fails or if local file was empty
    TRACKER_UUID = str(uuid.uuid4())
    log(f"⚠️ Failed to manage persistent UUID file (using ephemeral ID): {e}")

# Home Assistant API Configuration
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
API_URL = "http://supervisor/core/api/states/sensor.last_passing_ship_dev" if DEV_MODE else "http://supervisor/core/api/states/sensor.last_passing_ship"

# Dictionaries to track ships and rate limits
seen_ships = {}
last_map_update = {}
static_ship_data = {}
last_purge_time = datetime.now()
last_known_error = ""
current_conn_status = "Disconnected"
shutdown_in_progress = False

# Backoff variables to prevent AISStream API concurrency lockouts
RECONNECT_DELAY = 10
MAX_RECONNECT_DELAY = 125
reconnect_attempts = 0

# Map of AIS Navigational Status integers to human-readable strings
NAV_STATUS_MAP = {
    0: "Under way using engine", 1: "At anchor", 2: "Not under command",
    3: "Restricted manoeuvrability", 4: "Constrained by her draught",
    5: "Moored", 6: "Aground", 7: "Engaged in fishing",
    8: "Under way sailing", 14: "AIS-SART active", 15: "Not defined"
}

# Map of Navigational Status integers to MDI Icons
ICON_MAP = {
    0: "mdi:ferry",
    1: "mdi:anchor",
    2: "mdi:lifebuoy",
    3: "mdi:lifebuoy",
    4: "mdi:lifebuoy",
    5: "mdi:pier",
    6: "mdi:lifebuoy",
    7: "mdi:fish",
    8: "mdi:sail-boat",
    14: "mdi:lifebuoy"
}

def get_vessel_type_string(type_int):
    if not isinstance(type_int, int): return None
    if 20 <= type_int <= 29: return "Wing in ground (WIG)"
    if type_int == 30: return "Fishing"
    if type_int in (31, 32): return "Towing"
    if type_int == 33: return "Dredging"
    if type_int == 34: return "Diving Ops"
    if type_int == 35: return "Military Ops"
    if type_int == 36: return "Sailing"
    if type_int == 37: return "Pleasure Craft"
    if 40 <= type_int <= 49: return "High-Speed Craft"
    if type_int == 50: return "Pilot Vessel"
    if type_int == 51: return "Search and Rescue"
    if type_int == 52: return "Tug"
    if type_int == 53: return "Port Tender"
    if type_int == 54: return "Anti-pollution Equipment"
    if type_int == 55: return "Law Enforcement"
    if 60 <= type_int <= 69: return "Passenger Ship"
    if 70 <= type_int <= 79: return "Cargo Ship"
    if 80 <= type_int <= 89: return "Tanker"
    if 90 <= type_int <= 99: return "Other"
    return None

def sync_state_on_startup():
    if not SUPERVISOR_TOKEN:
        log("⚠️ SUPERVISOR_TOKEN is not set. Home Assistant API integration is disabled (running in standalone mode?).")
        return
        
    log("🔄 Synchronising Add-on memory with Home Assistant database...")
    api_url = "http://supervisor/core/api/states"
    headers = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}
    
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            states = json.loads(response.read().decode('utf-8'))
            
        restored_count = 0
        purged_count = 0
        for state in states:
            entity_id = state.get("entity_id", "")
            is_dev_entity = entity_id.endswith("_dev")
            
            # 1. Purge mismatched static entities
            if entity_id.startswith("sensor.last_passing_ship") or entity_id.startswith("sensor.ais_connection_status"):
                if is_dev_entity != DEV_MODE:
                    purge_url = f"http://supervisor/core/api/states/{entity_id}"
                    payload = {"state": "unavailable", "attributes": {}}
                    data = json.dumps(payload).encode('utf-8')
                    req = urllib.request.Request(purge_url, data=data, headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"}, method='POST')
                    try:
                        urllib.request.urlopen(req, timeout=5)
                        log(f"   ↳ Purged obsolete environment entity: {entity_id}")
                    except: pass
                continue
                
            # Target dynamic map entities, but rigorously protect last_passing_ship
            if entity_id.startswith("sensor.ais_ship_") and "last_passing_ship" not in entity_id:
                attrs = state.get("attributes", {})
                vessel_class = attrs.get("vessel_class", "Unknown")
                mmsi = str(attrs.get("mmsi")) if attrs.get("mmsi") else entity_id.replace("sensor.ais_ship_", "").replace("_dev", "")
                spotted_time = attrs.get("spotted_time")
                
                if not spotted_time:
                    continue
                    
                try:
                    parsed_time = datetime.strptime(spotted_time, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                    
                age_seconds = (datetime.now() - parsed_time).total_seconds()
                
                if (
                    not ENABLE_MAP_ENTITIES or 
                    CLEAR_MAP_ON_STARTUP or 
                    age_seconds > (MAP_TIMEOUT_MINUTES * 60) or
                    (not INCLUDE_CLASS_B and vessel_class == "Class B") or
                    (is_dev_entity != DEV_MODE) or
                    (watchlist_mmsis and mmsi not in watchlist_mmsis)
                ):
                    purge_url = f"http://supervisor/core/api/states/{entity_id}"
                    payload = {"state": "unavailable", "attributes": {}}
                    data = json.dumps(payload).encode('utf-8')
                    purge_req = urllib.request.Request(purge_url, data=data, headers=headers, method='POST')
                    
                    try:
                        urllib.request.urlopen(purge_req, timeout=5)
                        purged_count += 1
                        log(f"   ↳ Purged MMSI {mmsi} (Age: {int(age_seconds/60)}m)")
                    except Exception as purge_err:
                        log(f"Failed to purge entity {entity_id}: {purge_err}")
                else:
                    seen_ships[mmsi] = parsed_time
                    last_map_update[mmsi] = parsed_time
                    
                    static_data = {}
                    for key in ["destination", "eta", "ship_length", "imo_number", "call_sign", "vessel_type"]:
                        if key in attrs and attrs[key] is not None and attrs[key] != "":
                            static_data[key] = attrs[key]
                            
                    if static_data:
                        static_ship_data[mmsi] = static_data
                        
                    restored_count += 1
                    log(f"   ↳ Restored MMSI {mmsi} to memory (Age: {int(age_seconds/60)}m)")
                
        log(f"✅ Sync complete. Restored: {restored_count} active ships. Purged: {purged_count} stale ships.")
    except Exception as e:
        log(f"⚠️ Failed to complete startup sync: {e}")

def update_map_entity(ship_data, remove=False):
    if not SUPERVISOR_TOKEN:
        return
    if not ENABLE_MAP_ENTITIES and not remove:
        return

    mmsi = str(ship_data.get("mmsi", ""))
    if not mmsi:
        return

    entity_id = f"sensor.ais_ship_{mmsi}_dev" if DEV_MODE else f"sensor.ais_ship_{mmsi}"
    api_url = f"http://supervisor/core/api/states/{entity_id}"
    
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    
    if remove:
        payload = {
            "state": "unavailable",
            "attributes": {}
        }
    else:
        # Prevent "None" from becoming the state string if sog is missing
        speed = ship_data.get("sog")
        payload = {
            "state": str(speed) if speed is not None else "0",
            "attributes": {
                "friendly_name": ship_data.get("name", "Unknown Ship"),
                "ship_name": ship_data.get("name", "Unknown Ship"),
                "mmsi": str(ship_data.get("mmsi", "")),
                "spotted_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "latitude": ship_data.get("latitude"),
                "longitude": ship_data.get("longitude"),
                "speed_knots": ship_data.get("sog"),
                "course": ship_data.get("cog"),
                "heading": ship_data.get("heading"),
                "navigational_status": ship_data.get("nav_status_string"),
                "vessel_class": ship_data.get("vessel_class", "Unknown"),
                "icon": ship_data.get("icon", "mdi:ferry")
            }
        }
        
        static_info = static_ship_data.get(ship_data.get("mmsi"))
        if static_info:
            if "destination" in static_info and static_info["destination"]:
                payload["attributes"]["destination"] = static_info["destination"]
            if "eta" in static_info and static_info["eta"]:
                payload["attributes"]["eta"] = static_info["eta"]
            if "ship_length" in static_info and static_info["ship_length"] is not None:
                payload["attributes"]["ship_length"] = static_info["ship_length"]
            if "imo_number" in static_info and static_info["imo_number"] is not None:
                payload["attributes"]["imo_number"] = static_info["imo_number"]
            if "call_sign" in static_info and static_info["call_sign"]:
                payload["attributes"]["call_sign"] = static_info["call_sign"]
            if "vessel_type" in static_info and static_info["vessel_type"]:
                payload["attributes"]["vessel_type"] = static_info["vessel_type"]
        
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(api_url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as response:
            if remove:
                log(f"   ↳ HA API: Removed map entity {entity_id}")
            else:
                log(f"   ↳ HA API: Updated map entity {entity_id} (State: {payload['state']} SOG)")
    except Exception as e:
        log(f"Failed to update entity for MMSI {mmsi}: {e}")

def purge_old_ships():
   # Removes ships from memory and the map that haven't been seen recently 
    now = datetime.now()
    expired_mmsi = [
        mmsi for mmsi, last_seen in seen_ships.items() 
        if now - last_seen > timedelta(minutes=MAP_TIMEOUT_MINUTES)
    ]
    for mmsi in expired_mmsi:
        del seen_ships[mmsi]
        if mmsi in last_map_update:
            del last_map_update[mmsi]
        if mmsi in static_ship_data:
            del static_ship_data[mmsi]
            
        # Strip entity from the map
        update_map_entity({"mmsi": mmsi}, remove=True)
    
    if expired_mmsi:
        log(f"🧹 Purged {len(expired_mmsi)} stale ships from memory and any maps.")

def update_ha_entity(ship_data):
    if not SUPERVISOR_TOKEN:
        log("⚠️ SUPERVISOR_TOKEN not found. Are you running this inside a HA Add-on?")
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
            "icon": ship_data.get("icon", "mdi:ferry"),
            "latitude": ship_data.get("latitude"),
            "longitude": ship_data.get("longitude"),
            "speed_knots": ship_data.get("sog"),
            "course": ship_data.get("cog"),
            "heading": ship_data.get("heading"),
            "navigational_status": ship_data.get("nav_status_string"),
            "vessel_class": ship_data.get("vessel_class", "Unknown")
        }
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(API_URL, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=10) as response:
            entity_id = "sensor.last_passing_ship_dev" if DEV_MODE else "sensor.last_passing_ship"
            log(f"   ↳ HA API: Updated last passing ship entity {entity_id} (State: {payload['state']})")
            
    except urllib.error.URLError as e:
        log(f"Failed to update Home Assistant API: {e}")

# Background Monitoring State
api_monitor_state = {
    "state": "Unknown",
    "lastChecked": None,
    "lastMessageReceived": None,
    "error": None
}

def update_conn_status(status, new_error=None):
    global last_known_error
    global current_conn_status
    
    current_conn_status = status
    
    if not SUPERVISOR_TOKEN:
        return

    entity_id = "sensor.ais_connection_status_dev" if DEV_MODE else "sensor.ais_connection_status"
    api_url = f"http://supervisor/core/api/states/{entity_id}"
    
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }

    if new_error is not None:
        last_known_error = new_error

    sanitised_error = ""
    if last_known_error:
        # Only attempt to redact if the API key actually has characters in it
        if AIS_API_KEY:
            sanitised_error = str(last_known_error).replace(AIS_API_KEY, "[REDACTED]")
        else:
            sanitised_error = str(last_known_error)

    if ENABLE_API_MONITORING:
        # Set state to what was fetched from the API
        state_value = api_monitor_state["state"]
        
        # Use appropriate icon depending on the API state
        state_lower = str(state_value).lower()
        if "up" in state_lower:
            icon = "mdi:api"
        elif "down" in state_lower or "silent" in state_lower or "auth" in state_lower or "error" in state_lower or "unavailable" in state_lower:
            icon = "mdi:api-off"
        else:
            icon = "mdi:cloud-off-outline"
            
        attributes = {
            "friendly_name": "AIS Ship Tracker Connection Status (Dev)" if DEV_MODE else "AIS Ship Tracker Connection Status",
            "last_update_attempt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "websocket_status": status,
            "websocket_error": sanitised_error,
            "monitored_url": API_MONITORING_URL,
            "lastChecked": api_monitor_state["lastChecked"],
            "lastMessageReceived": api_monitor_state["lastMessageReceived"],
            "api_error": api_monitor_state["error"],
            "icon": icon
        }
    else:
        state_value = status
        if status == "Connected":
            icon = "mdi:api"
        elif status in ["Connecting", "Reconnecting"]:
            icon = "mdi:api-off"
        else:
            icon = "mdi:cloud-off-outline"
            
        attributes = {
            "friendly_name": "AIS Ship Tracker Connection Status (Dev)" if DEV_MODE else "AIS Ship Tracker Connection Status",
            "last_update_attempt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error_message": sanitised_error,
            "icon": icon
        }

    payload = {
        "state": state_value,
        "attributes": attributes
    }
    
    def send_status_update():
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(api_url, data=data, headers=headers, method='POST')
            # 5-second timeout requirement to ensure loop doesn't hang
            with urllib.request.urlopen(req, timeout=5) as response:
                pass
        except Exception as e:
            log(f"Failed to update connection status entity: {e}")

    threading.Thread(target=send_status_update, daemon=True).start()

# Periodic background thread for checking the external API
def api_monitor_worker():
    import threading
    
    def check_api():
        while True:
            if not ENABLE_API_MONITORING:
                time.sleep(10)
                continue
                
            # Build the anonymous telemetry payload
            telemetry_payload = {
                "uuid": TRACKER_UUID,
                "version": VERSION,
                "enable_map_entities": ENABLE_MAP_ENTITIES,
                "include_class_b": INCLUDE_CLASS_B,
                "clear_map_on_startup": CLEAR_MAP_ON_STARTUP,
                "map_timeout_minutes": MAP_TIMEOUT_MINUTES,
                "enable_api_monitoring": ENABLE_API_MONITORING,
                "watchlist_count": len(watchlist_mmsis)
            }
            
            try:
                # 1. Attempt POST with Telemetry
                data = json.dumps(telemetry_payload).encode('utf-8')
                req = urllib.request.Request(
                    API_MONITORING_URL, 
                    data=data,
                    headers={
                        "User-Agent": "AIS-Ship-Tracker-Addon",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as http_err:
                # Helper to update HA sensor state on failure
                api_monitor_state["state"] = "Status Unavailable"
                api_monitor_state["error"] = str(http_err)
                update_conn_status(current_conn_status)

                # Fallback: If 405 Method Not Allowed or 400 Bad Request, retry as standard GET
                if http_err.code in [400, 405]:
                    log(f"Uptime URL does not support POST (Status {http_err.code}). Falling back to GET.")
                    try:
                        req = urllib.request.Request(API_MONITORING_URL, headers={"User-Agent": "AIS-Ship-Tracker-Addon"})
                        with urllib.request.urlopen(req, timeout=10) as response:
                            res_data = json.loads(response.read().decode('utf-8'))
                    except Exception as fallback_err:
                        log(f"Failed fallback GET check: {fallback_err}")
                        api_monitor_state["error"] = str(fallback_err)
                        update_conn_status(current_conn_status)
                        time.sleep(API_MONITORING_INTERVAL)
                        continue
                else:
                    log(f"API monitoring HTTP error: {http_err}")
                    time.sleep(API_MONITORING_INTERVAL)
                    continue
            except Exception as e:
                log(f"API monitoring connection error: {e}")
                api_monitor_state["state"] = "Status Unavailable"
                api_monitor_state["error"] = str(e)
                update_conn_status(current_conn_status)
                time.sleep(API_MONITORING_INTERVAL)
                continue

            # Dynamically use whatever "state" key returns without hardcoding values
            api_state = res_data.get("state", "Unknown")
            last_checked_str = res_data.get("lastChecked")
            last_msg_str = res_data.get("lastMessageReceived")
            
            # Verify age of timestamps
            stale = False
            for ts_str in [last_checked_str, last_msg_str]:
                if ts_str:
                    try:
                        # Clean up ISO formats ending with Z or offset
                        clean_ts = ts_str.replace("Z", "+00:00")
                        # Try parsing with datetime.fromisoformat
                        ts_dt = datetime.fromisoformat(clean_ts)
                        # Get current UTC time
                        utc_now = datetime.now(tz=ts_dt.tzinfo)
                        age_seconds = (utc_now - ts_dt).total_seconds()
                        if age_seconds > (API_MONITORING_INTERVAL * 5):
                            stale = True
                    except Exception as parse_err:
                        # Fallback if parsing fails - don't mark stale
                        pass
                        
            if api_state.lower() == "down":
                new_state = "AISStream Service Down"
            elif stale:
                new_state = "No Vessel Data"
            else:
                new_state = api_state
                
            if new_state != api_monitor_state["state"]:
                log(f"API status changed from {api_monitor_state['state']} to {new_state}")
            
            api_monitor_state["state"] = new_state
            api_monitor_state["lastChecked"] = last_checked_str
            api_monitor_state["lastMessageReceived"] = last_msg_str
            api_monitor_state["error"] = None
            
            # Trigger Home Assistant entity update with the latest statuses
            update_conn_status(current_conn_status)
            
            time.sleep(API_MONITORING_INTERVAL)

    t = threading.Thread(target=check_api, daemon=True)
    t.start()

# Start the background monitor thread on startup
if ENABLE_API_MONITORING:
    api_monitor_worker()


def on_message(ws, message_json):
    global last_known_error
    try:
        message = json.loads(message_json)
        
        # Intercept and handle AISStream API Logic Errors gracefully
        if message.get("Type") == "Error":
            extracted_message = message.get("Message", "Unknown Error")
            log(f"⚠️ AISStream API Error: {extracted_message}")
            update_conn_status("Reconnecting", new_error=extracted_message)
            return
            
        msg_type = message.get("MessageType")
        
        if msg_type == "ShipStaticData":
            mmsi = message.get("MetaData", {}).get("MMSI")
            if mmsi:
                static_msg = message.get("Message", {}).get("ShipStaticData", {})
                dest = static_msg.get("Destination")
                raw_eta = static_msg.get("Eta")
                
                eta = None
                if isinstance(raw_eta, dict):
                    month = raw_eta.get("Month", 0)
                    day = raw_eta.get("Day", 0)
                    hour = raw_eta.get("Hour", 0)
                    minute = raw_eta.get("Minute", 0)
                    if month > 0 and day > 0:
                        eta = f"{day:02d}/{month:02d} {hour:02d}:{minute:02d} UTC"

                dim = static_msg.get("Dimension", {})
                
                ship_length = None
                if dim:
                    to_bow = dim.get("A")
                    to_stern = dim.get("B")
                    if to_bow is not None and to_stern is not None:
                        ship_length = to_bow + to_stern
                
                if dest:
                    dest = dest.strip()
                    
                raw_imo = static_msg.get("ImoNumber")
                imo_number = str(raw_imo) if isinstance(raw_imo, int) and raw_imo > 0 else None
                
                raw_call_sign = static_msg.get("CallSign")
                call_sign = None
                if isinstance(raw_call_sign, str):
                    stripped_cs = raw_call_sign.strip()
                    if stripped_cs and stripped_cs.isalnum():
                        call_sign = stripped_cs
                        
                raw_type = static_msg.get("Type")
                vessel_type = get_vessel_type_string(raw_type)
                
                is_new = mmsi not in static_ship_data
                
                static_data = {}
                if dest:
                    static_data["destination"] = dest
                if eta:
                    static_data["eta"] = eta
                if ship_length is not None:
                    static_data["ship_length"] = ship_length
                if imo_number is not None:
                    static_data["imo_number"] = imo_number
                if call_sign is not None:
                    static_data["call_sign"] = call_sign
                if vessel_type is not None:
                    static_data["vessel_type"] = vessel_type
                    
                if is_new and static_data:
                    ship_len_str = f"{ship_length}m" if ship_length is not None else "Unknown"
                    log(f"📋 Added new static data for MMSI {mmsi} (Dest: {dest}, ETA: {eta}, Length: {ship_len_str}, Type: {vessel_type})")
                
                if static_data:
                    static_ship_data[mmsi] = static_data
                    
            return
            
        # Determine vessel class based on message type
        if msg_type == "PositionReport":
            vessel_class = "Class A"
        elif msg_type in ["StandardClassBPositionReport", "ExtendedClassBPositionReport"]:
            vessel_class = "Class B"
        else:
            vessel_class = "Unknown"
        
        if msg_type in ["PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"]:
            # Clear the sticky error upon receiving valid data
            if last_known_error != "":
                last_known_error = ""
                update_conn_status("Connected")

            mmsi = message["MetaData"]["MMSI"]
            name = message["MetaData"]["ShipName"].strip() or "Unknown Ship Name"
            
            # Extract additional telemetry data dynamically based on the specific message type
            pos_report = message.get("Message", {}).get(msg_type, {})
            nav_status_int = pos_report.get("NavigationalStatus")
            
            # Build comprehensive ship data dictionary with unified defaults
            ship_data = {
                "name": name,
                "mmsi": mmsi,
                "latitude": pos_report.get("Latitude"),
                "longitude": pos_report.get("Longitude"),
                "sog": pos_report.get("Sog"),
                "cog": pos_report.get("Cog"),
                "heading": pos_report.get("TrueHeading"),
                "nav_status_string": NAV_STATUS_MAP.get(nav_status_int, "Not defined"),
                "vessel_class": vessel_class,
                "icon": ICON_MAP.get(nav_status_int, "mdi:ferry")
            }
            
            # 1. Logic for 'Last Passing Ship' (Triggers only on newly spotted ships)
            if mmsi not in seen_ships:
                log(f"🚢 NEW SHIP: {name} ({vessel_class} | MMSI: {mmsi})")
                log(f"   ↳ Telemetry -> Lat: {ship_data['latitude']}, Lon: {ship_data['longitude']}, "
                    f"Speed: {ship_data['sog']}kn, Course: {ship_data['cog']}°, "
                    f"Heading: {ship_data['heading']}°, Status: {ship_data['nav_status_string']}")
                update_ha_entity(ship_data)
            
            # Update last seen timestamp for memory persistence
            now = datetime.now()
            seen_ships[mmsi] = now
            
            # 2. Logic for Dynamic Map Entities (Updates live as ship moves, with anti-spam rate limiting)
            last_updated = last_map_update.get(mmsi)
            if last_updated is None or (now - last_updated).total_seconds() >= 60:
                update_map_entity(ship_data)
                last_map_update[mmsi] = now
                
                # If it's not a brand new ship, log the 60-second update so we can verify it's working
                if last_updated is not None:
                    log(f"🗺️ Ship Updated: {name} ({vessel_class} | MMSI: {mmsi}) | Lat: {ship_data.get('latitude')}, Lon: {ship_data.get('longitude')}")
                
    except json.JSONDecodeError as e:
        log(f"JSON Decode Error: Received malformed data from AISStream - {e}")
    except KeyError as e:
        log(f"Key Error: Missing expected data key in payload - {e}")
    except Exception as e:
        log(f"Unexpected error parsing data: {e}")

def on_error(ws, error):
    log(f"WebSocket Error: {error}")
    update_conn_status("Disconnected", new_error=str(error))

def on_close(ws, close_status_code, close_msg):
    if shutdown_in_progress:
        log("❌ Connection closed (Shutdown in progress).")
        return

    log("❌ Connection closed by server. Will attempt to reconnect...")
    
    # Add a helpful hint if the server drops us instantly without a word (usually an API key issue)
    if close_status_code is None and close_msg is None:
        error_reason = "Closed by server silently (Code: None). Check your API Key or go to https://aisuptime.buttermilkgreen.fyi/ for service status."
    else:
        safe_msg = close_msg if close_msg is not None else "No message provided"
        error_reason = f"Closed by server. Code: {close_status_code} - Msg: {safe_msg}"
        
    log(f"⚠️ Disconnect Reason: {error_reason}")
    update_conn_status("Disconnected", new_error=error_reason)

def on_pong(ws, message):
    global last_purge_time
    now = datetime.now()
    if (now - last_purge_time).total_seconds() >= 60:
        purge_old_ships()
        update_conn_status(current_conn_status)
        last_purge_time = now

def on_open(ws):
    global reconnect_attempts
    reconnect_attempts = 0
    log("🟢 Connected! Monitoring the water...")
    update_conn_status("Connected")
    
    filter_types = ["PositionReport", "ShipStaticData"]
    if INCLUDE_CLASS_B:
        filter_types.extend(["StandardClassBPositionReport", "ExtendedClassBPositionReport"])
        
    subscription_message = {
        "APIKey": AIS_API_KEY,
        "BoundingBoxes": BOUNDING_BOX,
        "FilterMessageTypes": filter_types
    }
    
    if watchlist_mmsis:
        subscription_message["FiltersShipMMSI"] = watchlist_mmsis
        
    ws.send(json.dumps(subscription_message))

def start_tracker():
    # Bounding Box Sanity Check
    lat_diff = abs(lat_north - lat_south)
    lon_diff = abs(lon_east - lon_west)
    if lat_diff > 3.0 or lon_diff > 3.0:
        log("⚠️ WARNING: Bounding box is extremely large. This may cause high API load and memory usage.")

    mode_str = "All Vessels (Class A & B)" if INCLUDE_CLASS_B else "Commercial Only (Class A)"
    log(f"🚢 Tracker Mode: {mode_str}")

    if watchlist_mmsis:
        log(f"🎯 Filtering active for {len(watchlist_mmsis)} MMSI(s).")
    else:
        log("🌐 Monitoring all vessels within the bounding box (no filters active).")

    if ENABLE_MAP_ENTITIES:
        log("🗺️ Multi-Ship Map Entities: ENABLED (individual vessel tracking entities will be created).")
    else:
        log("ℹ️ Multi-Ship Map Entities: DISABLED (only the 'last passing ship' and connection status entities will be updated).")

    env_str = "DEV" if DEV_MODE else "PROD"
    if DEV_MODE and WEBSOCKET_URL != "wss://stream.aisstream.io/v0/stream":
        log(f"[{env_str}] [{VERSION}] Connecting to custom websocket destination: {WEBSOCKET_URL}...")
    else:
        log(f"[{env_str}] [{VERSION}] Connecting to AISStream...")
        
    update_conn_status("Connecting")
    
    ws = websocket.WebSocketApp(
        WEBSOCKET_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_pong=on_pong
    )
    
    ws.run_forever(ping_interval=60, ping_timeout=10)

def graceful_shutdown(signum, frame):
    global shutdown_in_progress
    shutdown_in_progress = True
    log("🛑 Received stop signal from Home Assistant. Shutting down gracefully...")
    update_conn_status("Stopped", new_error="Add-on stopped by user or system.")
    log("🛑 Tracker safely stopped.")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    sync_state_on_startup()
        
    try:
        while True:
            start_tracker()
            update_conn_status("Reconnecting")
            
            reconnect_attempts += 1
            # Cap the exponent term at 4 since 2**4 = 16 (160s) already exceeds MAX_RECONNECT_DELAY (125s)
            exponent = min(reconnect_attempts - 1, 4)
            calculated_delay = RECONNECT_DELAY * (2 ** max(0, exponent))
            capped_delay = min(calculated_delay, MAX_RECONNECT_DELAY)
            # Apply randomized jitter
            jitter = random.uniform(0.85, 1.15)
            jittered_delay = capped_delay * jitter
            # Ensure the final delay is at least RECONNECT_DELAY seconds
            final_delay = max(RECONNECT_DELAY, jittered_delay)
            
            log(f"Reconnecting in {int(final_delay)} seconds (Attempt {reconnect_attempts})...")
            time.sleep(final_delay)
    except KeyboardInterrupt:
        log("🛑 Tracker stopped by user.")
        update_conn_status("Disconnected")