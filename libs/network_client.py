import network
import time
import config

try:
    import ntptime
except ImportError:
    ntptime = None

try:
    import requests
except ImportError:
    try:
        import urequests as requests
    except ImportError:
        requests = None

try:
    import json
except ImportError:
    import ujson as json

wlan = network.WLAN(network.STA_IF)

def connect_wifi(log_cb=None, timeout_ms=7000):
    if not wlan.active():
        wlan.active(True)
        
    if wlan.isconnected():
        return True
        
    if log_cb:
        log_cb("WIFI: CONNECTING...")
        
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    start_time = time.ticks_ms()
    
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start_time) > timeout_ms:
            if log_cb:
                log_cb("WIFI: TIMEOUT ERROR")
            wlan.active(False)
            return False
        time.sleep_ms(150)
        
    # Sync the system RTC clock through NTP if available
    if ntptime is not None:
        try:
            ntptime.settime()
        except Exception:
            pass  # Continue even in case of temporary NTP timeout

    if log_cb:
        log_cb(f"WIFI OK: {wlan.ifconfig()[0]}")
    return True

def disconnect_wifi(log_cb=None):
    if wlan.active():
        try:
            wlan.disconnect()
        except Exception:
            pass
        wlan.active(False)
        if log_cb:
            log_cb("WIFI: RADIO OFF")

def sync_session(score, focus_seconds, danger_count, last_rssi, battery=100, log_cb=None):
    if not connect_wifi(log_cb=log_cb):
        return False
        
    # Unix Timestamp in milliseconds
    current_timestamp = int(time.time() * 1000)
    
    payload = {
        "score": score,
        "focusSeconds": focus_seconds,
        "dangerCount": danger_count,
        "lastRssi": last_rssi,
        "battery": battery,
        "timestamp": current_timestamp
    }
    
    success = False
    try:
        headers = {"Content-Type": "application/json"}
        json_body = json.dumps(payload)
        
        if log_cb:
            log_cb("HTTP POST /sync...")
            
        if requests is not None:
            response = requests.post(config.BACKEND_URL, data=json_body, headers=headers, timeout=5)
            status = response.status_code
            response.close()
            
            if status in (200, 201, 204):
                if log_cb:
                    log_cb(f"HTTP OK ({status})")
                success = True
            else:
                if log_cb:
                    log_cb(f"HTTP ERR ({status})")
    except Exception as exc:
        if log_cb:
            log_cb("HTTP NET ERROR")
        print("[Sync] Error:", exc)
    finally:
        disconnect_wifi(log_cb=log_cb)
        time.sleep_ms(150)
        
    return success