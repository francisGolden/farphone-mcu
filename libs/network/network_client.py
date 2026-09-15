from libs.diagnostic_log import log as print
import socket
import json
import config
import network
import time
from libs.network.wifi_credentials import load_credentials, validate_backend_url
from libs.offline_storage import get_pending_syncs, clear_pending_syncs

wlan = network.WLAN(network.STA_IF)

def connect_wifi(log_cb=None, timeout_ms=9000):
    wifi_started = time.ticks_ms()
    credentials = load_credentials()
    if credentials is None:
        if log_cb:
            log_cb("WIFI: NOT CONFIGURED")
        return False
    if not wlan.active():
        wlan.active(True)
    if wlan.isconnected():
        print("[WiFi] Connected; IP / mask / gateway / DNS:", wlan.ifconfig())
        return True
    if log_cb:
        log_cb("WIFI: CONNECTING...")
    wlan.connect(credentials["ssid"], credentials["password"])
    start = time.ticks_ms()
    print("[Timing] WiFi start:", time.ticks_diff(start, wifi_started), "ms")
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            if log_cb:
                log_cb("WIFI: TIMEOUT")
            return False
        time.sleep_ms(150)
    print("[Timing] WiFi ready:", time.ticks_diff(time.ticks_ms(), wifi_started), "ms")
    print("[WiFi] Connected; IP / mask / gateway / DNS:", wlan.ifconfig())
    if log_cb:
        log_cb("WIFI OK")
    return True

def disconnect_wifi(log_cb=None):
    try:
        if wlan.isconnected():
            wlan.disconnect()
    except Exception:
        pass
    # Disconnecting alone leaves the station interface powered.
    wlan.active(False)
    if log_cb:
        log_cb("WIFI: OFF")

def _parse_url():
    credentials = load_credentials() or {}
    # Older devices can keep using config.py until setup is run again.
    backend_url = credentials.get('backend_url') or getattr(config, 'BACKEND_URL', '')
    clean_url = validate_backend_url(backend_url)[7:]
    if ":" in clean_url:
        host, port_str = clean_url.split(":")
        port = int(port_str.split("/")[0])
    else:
        host = clean_url.split("/")[0]
        port = 80
    return host, port

def _raw_tcp_request(method, path, payload=None, timeout=6.0):
    """Executes a pure TCP socket HTTP/1.0 request."""
    request_started = time.ticks_ms()
    host, port = _parse_url()
    s = None
    stage = "DNS resolution"
    try:
        print("[HTTP] Resolving:", host, "port:", port)
        phase_started = time.ticks_ms()
        addr = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][-1]
        print("[Timing]", method, "resolve:", time.ticks_diff(time.ticks_ms(), phase_started), "ms")
        s = socket.socket()
        s.settimeout(timeout)
        stage = "TCP connect"
        print("[HTTP] Connecting:", addr)
        phase_started = time.ticks_ms()
        s.connect(addr)
        print("[Timing]", method, "TCP connect:", time.ticks_diff(time.ticks_ms(), phase_started), "ms")

        headers = [
            f"{method} {path} HTTP/1.0",
            f"Host: {host}",
            "Connection: close",
            "Accept: application/json"
        ]

        body_bytes = b""
        if payload is not None:
            body_bytes = json.dumps(payload).encode("utf-8")
            headers.append("Content-Type: application/json")
            headers.append(f"Content-Length: {len(body_bytes)}")

        req_str = "\r\n".join(headers) + "\r\n\r\n"
        stage = "HTTP send"
        print("[HTTP] Sending:", method)
        phase_started = time.ticks_ms()
        s.sendall(req_str.encode("utf-8"))
        if body_bytes:
            s.sendall(body_bytes)

        print("[Timing]", method, "send:", time.ticks_diff(time.ticks_ms(), phase_started), "ms")
        phase_started = time.ticks_ms()
        stage = "HTTP receive"
        print("[HTTP] Waiting for response")
        res_bytes = b""
        while True:
            chunk = s.recv(512)
            if not chunk:
                break
            if not res_bytes:
                print("[Timing]", method, "first byte:", time.ticks_diff(time.ticks_ms(), phase_started), "ms")
            res_bytes += chunk
        print("[Timing]", method, "response including close:", time.ticks_diff(time.ticks_ms(), phase_started), "ms")
        print("[Timing]", method, "total:", time.ticks_diff(time.ticks_ms(), request_started), "ms")
    except OSError as exc:
        print("[HTTP] Failed at", stage, ":", exc)
        raise
    finally:
        if s is not None:
            s.close()

    raw_resp = res_bytes.decode("utf-8")
    status_line = raw_resp.split("\r\n")[0] if raw_resp else ""
    body = raw_resp.split("\r\n\r\n", 1)[1].strip() if "\r\n\r\n" in raw_resp else ""
    return status_line, body

def fetch_user_raw(user_id):
    """Fetches user profile (assumes Wi-Fi is already connected)."""
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

def send_harvest_raw(user_id, seed_identifier, plant_identifier, xp_earned, harvestOutcome, duration_seconds, peek_count, first_peek_sec):
    """Sends harvest/session event over an established connection."""
    payload = {
        "userId": user_id,
        "seedIdentifier": seed_identifier,
        "plantIdentifier": plant_identifier,
        "xpEarned": xp_earned,
        "harvestOutcome": harvestOutcome,
        "durationSeconds": duration_seconds,
        "peekCount": peek_count,
        "firstPeekSec": first_peek_sec
    }
    status, body = _raw_tcp_request("POST", "/api/harvest", payload=payload)
    print(f"[HTTP POST /api/harvest] Status: {status} | Body: {body}")
    return "200" in status

def sync_session_event(user_id, seed_identifier, plant_identifier, xp_earned, harvestOutcome, duration_seconds, peek_count=0, first_peek_sec=None,log_cb=None, timings=None):
    """
    Connects to Wi-Fi, delivers session outcome telemetry (SUCCESSFUL or FAILED),
    refreshes user profile on SUCCESSFUL completions, and cleanly tears down Wi-Fi.
    """
    if timings is not None:
        timings.clear()

    def measured(name, fn, *args, **kwargs):
        if timings is None:
            return fn(*args, **kwargs)
        started = time.ticks_ms()
        try:
            return fn(*args, **kwargs)
        finally:
            timings[name] = time.ticks_diff(time.ticks_ms(), started)

    try:
        if not measured('wifi', connect_wifi, log_cb=log_cb):
            return None

        ok = measured('post', send_harvest_raw, user_id, seed_identifier, plant_identifier, xp_earned, harvestOutcome, duration_seconds, peek_count, first_peek_sec)
        if ok and harvestOutcome == "SUCCESSFUL":
            if log_cb:
                log_cb("SYNC PROFILE...")
            profile = measured('get', fetch_user_raw, user_id)
            return profile if profile else True
        return ok
    except Exception as e:
        print("[Session API] Err:", e)
        return False
    finally:
        measured('off', disconnect_wifi, log_cb=log_cb)

def initial_sync(user_id, log_cb=None):
    """Flushes offline logs and retrieves fresh user profile at boot."""
    try:
        if not connect_wifi(log_cb=log_cb):
            return None

        pending = get_pending_syncs()
        if pending:
            print(f"[Init Sync] Flushing {len(pending)} offline records...")
            if log_cb:
                log_cb(f"SYNC OFFLINE ({len(pending)})...")
            remaining = []
            for item in pending:
                try:
                    seed = item.get("seedIdentifier")
                    plant = item.get("plantIdentifier")
                    score = item.get("xpEarned", 0)
                    harvestOutcome = item.get("harvestOutcome", "SUCCESSFUL")
                    duration = item.get("durationSeconds", 0)
                    peeks = item.get("peekCount", 0)
                    first_p = item.get("firstPeekSec")

                    ok = send_harvest_raw(user_id, seed, plant, score, harvestOutcome, duration, peeks, first_p)
                    if not ok:
                        remaining.append(item)
                except Exception as ex:
                    print("[Init Sync] Err sending item:", ex)
                    remaining.append(item)

            if not remaining:
                clear_pending_syncs()
                print("[Init Sync] Offline queue emptied successfully.")
            else:
                try:
                    with open("pending_sync.json", "w") as f:
                        json.dump(remaining, f)
                except Exception:
                    pass

        if log_cb:
            log_cb("FETCHING PROFILE...")
        return fetch_user_raw(user_id)

    except Exception as exc:
        print("[Init Sync] General error:", exc)
        return None
    finally:
        disconnect_wifi(log_cb=log_cb)
