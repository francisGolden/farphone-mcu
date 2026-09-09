import network
import time
import config
import socket

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
wlan.active(False)

# ==============================================================================
# GESTIONE WI-FI ON-DEMAND
# ==============================================================================
def connect_wifi(log_cb=None, timeout_ms=8000):
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
                log_cb("WIFI: TIMEOUT")
            wlan.active(False)
            return False
        time.sleep_ms(150)

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

# ==============================================================================
# 1. GET USER PROFILE (All'avvio dell'app)
# ==============================================================================
def get_user_profile(user_id, log_cb=None):
    """
    Recupera il profilo utente tramite GET /api/user?id={user_id}.
    Gestisce in modo sicuro sia risposte strutturate JSON (dict) 
    sia risposte scalari (bool).
    """
    if not connect_wifi(log_cb=log_cb):
        return None

    user_data = None
    
    # 1. Parsing di host e porta dall'URL (es. "http://192.168.1.50:8080")
    clean_url = config.BACKEND_URL.replace("http://", "").replace("https://", "").rstrip("/")
    if ":" in clean_url:
        host, port_str = clean_url.split(":")
        port = int(port_str.split("/")[0])
    else:
        host = clean_url.split("/")[0]
        port = 80

    path = f"/api/user?id={user_id}"

    try:
        if log_cb:
            log_cb("CONNECTING TCP...")

        # 2. Connessione TCP Socket
        addr = socket.getaddrinfo(host, port)[0][-1]
        s = socket.socket()
        s.settimeout(6.0)
        s.connect(addr)

        # Usiamo HTTP/1.0 per forzare la chiusura a fine stream ed evitare Transfer-Encoding: chunked
        http_req = (
            f"GET {path} HTTP/1.0\r\n"
            f"Host: {host}\r\n"
            f"Connection: close\r\n"
            f"Accept: application/json\r\n\r\n"
        )
        s.sendall(http_req.encode())

        # 3. Ricezione buffer completo
        response_bytes = b""
        while True:
            chunk = s.recv(512)
            if not chunk:
                break
            response_bytes += chunk
        s.close()

        raw_resp = response_bytes.decode("utf-8")
        print("=== RAW RESPONSE DALLO STICK ===")
        print(raw_resp)
        print("================================")

        # 4. Estrazione status code e separazione Header/Body
        if "\r\n\r\n" in raw_resp:
            headers_part, body = raw_resp.split("\r\n\r\n", 1)
        else:
            headers_part, body = "", raw_resp

        status_line = headers_part.split("\r\n")[0] if headers_part else ""
        if "200" not in status_line:
            print(f"[User API] HTTP Status non OK: {status_line}")
            if log_cb:
                log_cb("HTTP NON-200")
            return None

        # 5. Parsing JSON con protezione sul tipo
        body = body.strip()
        data = json.loads(body)
        print(f"[User API] Parsed type: {type(data)} -> {data}")

        if isinstance(data, dict):
            user_data = {
                "username": str(data.get("username", "User")),
                "totalPoints": int(data.get("totalPoints", 0))
            }
        elif isinstance(data, bool):
            if data:
                # Backend ha risposto solo 'true'
                user_data = {
                    "username": "Verified",
                    "totalPoints": 0
                }
            else:
                user_data = None
        else:
            print(f"[User API] Payload non riconosciuto: {data}")
            user_data = None

        if user_data and log_cb:
            log_cb(f"OK: {user_data['username']}")

    except Exception as exc:
        print("[User API] Socket Exception:", exc)
        if log_cb:
            log_cb("PARSING ERR")
    finally:
        disconnect_wifi(log_cb=log_cb)

    return user_data

# ==============================================================================
# 2. UPDATE USER POINTS (A fine sessione)
# ==============================================================================
def update_user_points(user_id, score_to_add, log_cb=None):
    """
    Interroga POST /api/user/update per incrementare i totalPoints.
    Ritorna True se l'aggiornamento è andato a buon fine, False altrimenti.
    """
    if not connect_wifi(log_cb=log_cb):
        return False

    url = f"{config.BACKEND_URL.rstrip('/')}/api/user/update"
    payload = {
        "id": user_id,
        "scoreToAdd": score_to_add
    }
    
    success = False
    try:
        headers = {"Content-Type": "application/json"}
        json_body = json.dumps(payload)

        if log_cb:
            log_cb(f"SYNC: +{score_to_add} PTS")

        if requests is not None:
            res = requests.post(url, data=json_body, headers=headers, timeout=6)
            if res.status_code in (200, 201, 204):
                success = True
                if log_cb:
                    log_cb("SYNC COMPLETE!")
            else:
                if log_cb:
                    log_cb(f"UPDATE ERR: {res.status_code}")
            res.close()
    except Exception as exc:
        if log_cb:
            log_cb("HTTP POST ERR")
        print("[User API] Update Error:", exc)
    finally:
        disconnect_wifi(log_cb=log_cb)

    return success