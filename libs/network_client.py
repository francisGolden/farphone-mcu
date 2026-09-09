import socket
import json
import config
import network
import time

wlan = network.WLAN(network.STA_IF)

def connect_wifi(log_cb=None, timeout_ms=8000):
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

def get_user_profile(user_id, log_cb=None):
    if not connect_wifi(log_cb=log_cb):
        return None
    user_data = None
    clean_url = config.BACKEND_URL.replace("http://", "").replace("https://", "").rstrip("/")
    host, port = (clean_url.split(":") if ":" in clean_url else (clean_url, "80"))
    port = int(port.split("/")[0])
    path = f"/api/user?id={user_id}"

    try:
        if log_cb:
            log_cb("CONNECTING TCP...")
        addr = socket.getaddrinfo(host, port)[0][-1]
        s = socket.socket()
        s.settimeout(6.0)
        s.connect(addr)
        http_req = (
            f"GET {path} HTTP/1.0\r\n"
            f"Host: {host}\r\n"
            f"Connection: close\r\n"
            f"Accept: application/json\r\n\r\n"
        )
        s.sendall(http_req.encode())
        res_bytes = b""
        while True:
            c = s.recv(512)
            if not c:
                break
            res_bytes += c
        s.close()

        raw_resp = res_bytes.decode("utf-8")
        body = raw_resp.split("\r\n\r\n", 1)[1].strip() if "\r\n\r\n" in raw_resp else raw_resp.strip()
        data = json.loads(body)

        if isinstance(data, dict):
            user_data = {
                "username": str(data.get("username", "Farmer")),
                "totalPoints": int(data.get("totalPoints", 0))
            }
        elif isinstance(data, bool):
            user_data = {"username": "Farmer", "totalPoints": 0} if data else None
    except Exception as exc:
        print("[User API] Socket Exception:", exc)
    finally:
        disconnect_wifi(log_cb=log_cb)

    return user_data

def update_user_points(user_id, score_to_add, plant_type=None, log_cb=None):
    if not connect_wifi(log_cb=log_cb):
        return False

    clean_url = config.BACKEND_URL.replace("http://", "").replace("https://", "").rstrip("/")
    host, port = (clean_url.split(":") if ":" in clean_url else (clean_url, "80"))
    port = int(port.split("/")[0])
    path = "/api/user/update"

    payload = {
        "id": user_id,
        "scoreToAdd": score_to_add,
        "plantType": plant_type  # Es. "PARSNIP", "BLUEBERRY", "ANCIENT_FRUIT", o None
    }
    json_body = json.dumps(payload)
    success = False

    try:
        if log_cb:
            log_cb(f"HARVEST: +{score_to_add} XP")
        addr = socket.getaddrinfo(host, port)[0][-1]
        s = socket.socket()
        s.settimeout(6.0)
        s.connect(addr)
        http_req = (
            f"POST {path} HTTP/1.0\r\n"
            f"Host: {host}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(json_body)}\r\n"
            f"Connection: close\r\n\r\n"
            f"{json_body}"
        )
        s.sendall(http_req.encode())
        res_bytes = b""
        while True:
            c = s.recv(512)
            if not c:
                break
            res_bytes += c
        s.close()

        raw_resp = res_bytes.decode("utf-8")
        if "200" in raw_resp.split("\r\n")[0]:
            success = True
    except Exception as exc:
        print("[Update API] Error:", exc)
    finally:
        disconnect_wifi(log_cb=log_cb)

    return success