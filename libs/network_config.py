import network
import time
import config

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
    """Activates Wi-Fi and connects with step-by-step progress logging."""
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
        
    ip_addr = wlan.ifconfig()[0]
    if log_cb:
        log_cb(f"WIFI OK: {ip_addr}")
    print("[Wi-Fi] Connected:", ip_addr)
    return True

def disconnect_wifi(log_cb=None):
    """Disconnects and disables the Wi-Fi radio."""
    if wlan.active():
        try:
            wlan.disconnect()
        except Exception:
            pass
        wlan.active(False)
        if log_cb:
            log_cb("WIFI: RADIO OFF")

def sync_session(score, focus_seconds, danger_count, last_rssi, battery=100, log_cb=None):
    """Safely connects Wi-Fi, posts telemetry with timeout, and releases radio."""
    if not connect_wifi(log_cb=log_cb):
        return False
        
    payload = {
        "score": score,
        "focusSeconds": focus_seconds,
        "dangerCount": danger_count,
        "lastRssi": last_rssi,
        "battery": battery
    }
    
    success = False
    try:
        headers = {"Content-Type": "application/json"}
        json_body = json.dumps(payload)
        
        if log_cb:
            log_cb("HTTP POST /sync...")
        print("[Sync] Sending:", json_body)
        
        if requests is not None:
            # timeout=5 avoid that the socket is blocked indefinitely
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
        else:
            if log_cb:
                log_cb("NO HTTP CLIENT")
                
    except Exception as exc:
        if log_cb:
            log_cb("NET TIMEOUT/ERR")
        print("[Sync] Exception during HTTP post:", exc)
    finally:
        disconnect_wifi(log_cb=log_cb)
        time.sleep_ms(150)  # Stabilize radio before returning to BLE
        
    return success