import socket
import json
import config
import network
import time
from libs.offline_storage import get_pending_syncs, clear_pending_syncs

wlan = network.WLAN(network.STA_IF)

def connect_wifi(log_cb=None, timeout_ms=9000):
    if not wlan.active():
        wlan.active(True)
    if wlan.isconnected():
        return True
    if log_cb:
        log_cb("WIFI: CONNECTING...")
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    start = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            if log_cb:
                log_cb("WIFI: TIMEOUT")
            return False
        time.sleep_ms(150)
    if log_cb:
        log_cb("WIFI OK")
    return True

def disconnect_wifi(log_cb=None):
    try:
        if wlan.isconnected():
            wlan.disconnect()
    except Exception:
        pass
    if log_cb:
        log_cb("WIFI: IDLE")

def _parse_url():
    clean_url = config.BACKEND_URL.replace("http://", "").replace("https://", "").rstrip("/")
    if ":" in clean_url:
        host, port_str = clean_url.split(":")
        port = int(port_str.split("/")[0])
    else:
        host = clean_url.split("/")[0]
        port = 80
    return host, port

def _raw_tcp_request(method, path, payload=None, timeout=6.0):
    """Pure TCP socket HTTP/1.0 call."""
    host, port = _parse_url()
    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket()
    s.settimeout(timeout)
    s.connect(addr)

    headers = [
        f"{method} {path} HTTP/1.0",
        f"Host: {host}",
        "Connection: close",
        "Accept: application/json"
    ]
    
    body_bytes = b""
    if payload:
        body_bytes = json.dumps(payload).encode("utf-8")
        headers.append("Content-Type: application/json")
        headers.append(f"Content-Length: {len(body_bytes)}")

    req_str = "\r\n".join(headers) + "\r\n\r\n"
    s.sendall(req_str.encode("utf-8"))
    if body_bytes:
        s.sendall(body_bytes)

    res_bytes = b""
    while True:
        chunk = s.recv(512)
        if not chunk:
            break
        res_bytes += chunk
    s.close()

    raw_resp = res_bytes.decode("utf-8")
    status_line = raw_resp.split("\r\n")[0] if raw_resp else ""
    body = raw_resp.split("\r\n\r\n", 1)[1].strip() if "\r\n\r\n" in raw_resp else ""
    return status_line, body

def fetch_user_raw(user_id):
    """Fetches user profile without managing Wi-Fi state."""
    status, body = _raw_tcp_request("GET", f"/api/user?id={user_id}")
    print(f"[HTTP GET /api/user] Status: {status} | Body: {body}")
    if "200" not in status:
        return None
    data = json.loads(body)
    if isinstance(data, dict):
        uname = data.get("username") or data.get("name") or "Farmer"
        pts = data.get("totalPoints") if data.get("totalPoints") is not None else data.get("score", 0)
        return {"username": str(uname), "totalPoints": int(pts)}
    return None

def send_update_raw(user_id, xp_earned, plant_identifier, seed_identifier):
    """Pushes harvest log without managing Wi-Fi state."""
    payload = {
        "userId": user_id,
        "xpEarned": xp_earned,
        "plantIdentifier": plant_identifier,
        "seedIdentifier": seed_identifier
    }
    status, body = _raw_tcp_request("POST", "/api/harvest", payload=payload)
    print(f"[HTTP POST /api/harvest] Status: {status} | Body: {body}")
    return "200" in status

# Synchronizes harvest and immediately retrieves fresh profile in a single Wi-Fi session
def update_user_points(user_id, xp_earned, plant_identifier=None, seed_identifier=None, log_cb=None):
    if not connect_wifi(log_cb=log_cb):
        return None  # Return None on connection failure
    try:
        ok = send_update_raw(user_id, xp_earned, plant_identifier, seed_identifier)
        if ok:
            if log_cb:
                log_cb("SYNC PROFILE...")
            # Retrieve fresh profile right away while Wi-Fi is hot
            fresh_profile = fetch_user_raw(user_id)
            return fresh_profile if fresh_profile else True
        return False
    except Exception as e:
        print("[Update API] Err:", e)
        return False
    finally:
        disconnect_wifi(log_cb=log_cb)

def initial_sync(user_id, log_cb=None):
    """
    1. Connects to Wi-Fi once
    2. Flushes offline queue
    3. Fetches fresh profile
    4. Disconnects Wi-Fi
    """
    if not connect_wifi(log_cb=log_cb):
        return None

    try:
        pending = get_pending_syncs()
        if pending:
            print(f"[Init Sync] Flushing {len(pending)} offline records...")
            if log_cb:
                log_cb(f"SYNC OFFLINE ({len(pending)})...")
            remaining = []
            for item in pending:
                try:
                    score = item.get("score") or item.get("xpEarned", 0)
                    plant = item.get("plantType") or item.get("plantIdentifier")
                    seed = item.get("seedIdentifier") or item.get("seed_id")
                    ok = send_update_raw(user_id, score, plant, seed)
                    if not ok:
                        remaining.append(item)
                except Exception as ex:
                    print("[Init Sync] Send record error:", ex)
                    remaining.append(item)
            
            if not remaining:
                clear_pending_syncs()
                print("[Init Sync] Offline queue completely emptied!")
            else:
                try:
                    with open("pending_sync.json", "w") as f:
                        json.dump(remaining, f)
                except Exception:
                    pass

        if log_cb:
            log_cb("FETCHING PROFILE...")
        profile = fetch_user_raw(user_id)
        return profile

    except Exception as exc:
        print("[Init Sync] General error:", exc)
        return None
    finally:
        disconnect_wifi(log_cb=log_cb)