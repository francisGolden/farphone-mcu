from libs.diagnostic_log import log as print
import socket
import json
import config
import network
import time
from libs.network.wifi_credentials import load_credentials, validate_backend_url
from libs.offline_storage import get_pending_syncs, clear_pending_syncs, replace_pending_syncs, acknowledge_event

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
            f"Host: {host}:{port}",
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
        expected_size = None
        headers_read = False
        while True:
            remaining_ms = int(timeout * 1000) - time.ticks_diff(time.ticks_ms(), request_started)
            if remaining_ms <= 0:
                raise OSError("HTTP total timeout")
            s.settimeout(remaining_ms / 1000)
            chunk = s.recv(512)
            if not chunk:
                if expected_size is not None and len(res_bytes) < expected_size:
                    raise OSError("Incomplete HTTP body")
                break
            if not res_bytes:
                print("[Timing]", method, "first byte:", time.ticks_diff(time.ticks_ms(), phase_started), "ms")
            res_bytes += chunk
            if len(res_bytes) > 32768:
                raise OSError('HTTP response too large')
            if not headers_read:
                boundary = res_bytes.find(b'\r\n\r\n')
                if boundary < 0:
                    if len(res_bytes) > 4096:
                        raise OSError('HTTP headers too large')
                else:
                    if boundary > 4096:
                        raise OSError('HTTP headers too large')
                    headers_read = True
                    fields = {}
                    for line in res_bytes[:boundary].split(b'\r\n')[1:]:
                        name, value = line.split(b':', 1)
                        fields[name.lower()] = value.strip()
                    if b'transfer-encoding' in fields:
                        raise OSError('Unsupported HTTP transfer encoding')
                    if b'content-length' in fields:
                        length = int(fields[b'content-length'])
                        expected_size = boundary + 4 + length
                        if length < 0 or expected_size > 32768:
                            raise OSError('Invalid HTTP content length')
            if expected_size is not None and len(res_bytes) >= expected_size:
                res_bytes = res_bytes[:expected_size]
                break
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
    if len(status.split()) < 2 or status.split()[1] != "200":
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
    return len(status.split()) >= 2 and status.split()[1] in ("200", "201", "204")

def sync_session_event(user_id, seed_identifier, plant_identifier, xp_earned, harvestOutcome, duration_seconds, peek_count=0, first_peek_sec=None,log_cb=None, timings=None, event_id=None):
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

    stage = 'WIFI'
    def progress(message):
        if timings is not None:
            # Connection messages contain fixed labels, never SSIDs or passwords.
            timings['wifi_status'] = message
        if log_cb:
            log_cb(message)

    try:
        if not measured('wifi', connect_wifi, log_cb=progress):
            if timings is not None:
                timings['error_stage'] = stage
                timings['error_code'] = timings.get('wifi_status', 'NOT CONNECTED')
            return None

        stage = 'POST'

        ok = measured('post', send_harvest_raw, user_id, seed_identifier, plant_identifier, xp_earned, harvestOutcome, duration_seconds, peek_count, first_peek_sec)
        if not ok and timings is not None:
            timings['error_stage'] = stage
            timings['error_code'] = 'HTTP REJECTED'
        if ok and event_id is not None:
            stage = 'LOCAL ACK'
            acknowledge_event(event_id)
        if ok and harvestOutcome == "SUCCESSFUL":
            if log_cb:
                log_cb("SYNC PROFILE...")
            try:
                profile = measured('get', fetch_user_raw, user_id)
                return profile if profile else True
            except Exception as exc:
                # POST is already acknowledged; a profile failure must not resend it.
                print('[Profile] Refresh failed after successful harvest:', exc)
                return True
        return ok
    except Exception as e:
        if timings is not None:
            timings['error_stage'] = stage
            args = getattr(e, 'args', ())
            # Exclude exception messages that might contain configuration data.
            timings['error_code'] = ('ERRNO ' + str(args[0])
                                     if args and isinstance(args[0], int)
                                     else type(e).__name__)
        print("[Session API] Err:", e)
        return False
    finally:
        try:
            measured('off', disconnect_wifi, log_cb=log_cb)
        except Exception as exc:
            # Cleanup failure cannot undo a server/local acknowledgement.
            if timings is not None:
                timings['cleanup_error'] = type(exc).__name__
            print('[WiFi] Shutdown failed:', exc)

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
            while pending:
                item = pending[0]
                # Migrate old records before transmission, keeping identity across retries.
                if not item.get('eventId'):
                    import os
                    import binascii
                    item['eventId'] = binascii.hexlify(os.urandom(16)).decode()
                    replace_pending_syncs(pending)
                ok = send_harvest_raw(user_id, item['seedIdentifier'],
                    item.get('plantIdentifier'), item.get('xpEarned', 0),
                    item.get('harvestOutcome', 'SUCCESSFUL'), item.get('durationSeconds', 0),
                    item.get('peekCount', 0), item.get('firstPeekSec'))
                if not ok:
                    break
                # Persist each acknowledgement, not just at the end of the batch.
                pending = pending[1:]
                replace_pending_syncs(pending)

        if log_cb:
            log_cb("FETCHING PROFILE...")
        return fetch_user_raw(user_id)

    except Exception as exc:
        print("[Init Sync] General error:", exc)
        return None
    finally:
        disconnect_wifi(log_cb=log_cb)
