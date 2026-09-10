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
    """Esegue una chiamata HTTP/1.0 pura via TCP Socket."""
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
    """Recupera profilo senza gestire il Wi-Fi (presuppone Wi-Fi già connesso)."""
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

def send_update_raw(user_id, score, plant_type):
    """Invia punti senza gestire il Wi-Fi (presuppone Wi-Fi già connesso)."""
    payload = {
        "id": user_id,
        "scoreToAdd": score,
        "plantType": plant_type
    }
    status, body = _raw_tcp_request("POST", "/api/user/update", payload=payload)
    print(f"[HTTP POST /api/user/update] Status: {status} | Body: {body}")
    return "200" in status

# Chiamata isolata utilizzata da complete_session durante il gioco
def update_user_points(user_id, score_to_add, plant_type=None, log_cb=None):
    if not connect_wifi(log_cb=log_cb):
        return False
    try:
        return send_update_raw(user_id, score_to_add, plant_type)
    except Exception as e:
        print("[Update API] Err:", e)
        return False
    finally:
        disconnect_wifi(log_cb=log_cb)

# FUNZIONE UNIFICATA DI BOOTSTRAP: Flush code offline + Get profilo in un colpo solo
def initial_sync(user_id, log_cb=None):
    """
    1. Si connette una sola volta al Wi-Fi
    2. Svuota la coda offline inviando le sessioni arretrate
    3. Recupera il profilo aggiornato
    4. Disconnette il Wi-Fi
    """
    if not connect_wifi(log_cb=log_cb):
        return None

    try:
        # 1. Flush della memoria flash
        pending = get_pending_syncs()
        if pending:
            print(f"[Init Sync] Trovati {len(pending)} raccolti offline da inviare...")
            if log_cb:
                log_cb(f"SYNC OFFLINE ({len(pending)})...")
            remaining = []
            for item in pending:
                try:
                    ok = send_update_raw(user_id, item["score"], item["plantType"])
                    if not ok:
                        remaining.append(item)
                except Exception as ex:
                    print("[Init Sync] Err singolo invio:", ex)
                    remaining.append(item)
            
            if not remaining:
                clear_pending_syncs()
                print("[Init Sync] Coda offline interamente svuotata!")
            else:
                # Sovrascrive mantenendo solo quelli falliti
                try:
                    with open("pending_sync.json", "w") as f:
                        json.dump(remaining, f)
                except Exception:
                    pass

        # 2. Lettura del profilo fresco dal backend
        if log_cb:
            log_cb("FETCHING PROFILE...")
        profile = fetch_user_raw(user_id)
        return profile

    except Exception as exc:
        print("[Init Sync] Errore generale:", exc)
        return None
    finally:
        disconnect_wifi(log_cb=log_cb)