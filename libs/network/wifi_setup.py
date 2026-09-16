"""Temporary, password-protected Wi-Fi setup page, served only during boot."""
import os
import binascii
import socket
import time
import network
from libs.network.wifi_credentials import save_credentials, validate, validate_backend_url


def decode_form(body):
    def decode(value):
        value = value.replace(b'+', b' ')
        result = bytearray()
        i = 0
        while i < len(value):
            if value[i] == 37:
                if i + 2 >= len(value):
                    raise ValueError('Invalid encoding')
                result.append(int(value[i + 1:i + 3], 16))
                i += 3
            else:
                result.append(value[i])
                i += 1
        return bytes(result).decode('utf-8')
    fields = {}
    for pair in body.split(b'&'):
        key, separator, value = pair.partition(b'=')
        if not separator:
            raise ValueError('Invalid form')
        fields[decode(key)] = decode(value)
    return fields


def read_request(client):
    # Bounded memory and total time, including clients sending one byte at a time.
    started = time.ticks_ms()
    data = b''
    while b'\r\n\r\n' not in data:
        if len(data) > 4096 or time.ticks_diff(time.ticks_ms(), started) > 3000:
            raise ValueError('Request too large or slow')
        chunk = client.recv(512)
        if not chunk:
            raise ValueError('Incomplete headers')
        data += chunk
    headers, body = data.split(b'\r\n\r\n', 1)
    if len(headers) > 4096:
        raise ValueError('Headers too large')
    lines = headers.decode('utf-8').split('\r\n')
    method, path, version = lines[0].split(' ')
    values = {}
    for line in lines[1:]:
        name, value = line.split(':', 1)
        values[name.lower()] = value.strip()
    length = int(values.get('content-length', '0'))
    if not 0 <= length <= 1024 or 'transfer-encoding' in values:
        raise ValueError('Unsupported body')
    while len(body) < length:
        if time.ticks_diff(time.ticks_ms(), started) > 3000:
            raise ValueError('Request too slow')
        chunk = client.recv(min(512, length - len(body)))
        if not chunk:
            raise ValueError('Incomplete body')
        body += chunk
    return method, path, body[:length]


def scan_networks(sta):
    """One scan per setup, before the phone joins the AP; strongest SSID first."""
    try:
        sta.active(True)
        strongest = {}
        for item in sta.scan():
            try:
                name = item[0].decode('utf-8')
                if not name or len(item[0]) > 32:
                    continue
                rssi = item[3]
                if name not in strongest or rssi > strongest[name]:
                    strongest[name] = rssi
            except (ValueError, IndexError, TypeError):
                continue
        return sorted(strongest, key=lambda name: strongest[name], reverse=True)[:30]
    except (OSError, AttributeError, NotImplementedError):
        return []
    finally:
        sta.active(False)


def html_escape(value):
    return value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')


def page(token, message='', networks=()):
    # SSIDs are untrusted radio input, including when used in option attributes.
    options = ''.join('<option value="' + html_escape(name) + '">' + html_escape(name) + '</option>' for name in networks)
    hint = 'Scegli una rete dall’elenco.' if networks else 'Nessuna rete rilevata. Inserisci il nome manualmente.'
    # message and token are internal strings; submitted credentials are never echoed.
    return '''<!doctype html><html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Farphone · Wi-Fi</title><style>
body{font:18px system-ui;background:#f3f7f1;color:#193825;margin:32px auto;padding:20px;max-width:420px}
label{display:block;margin-top:22px}input,select,button{box-sizing:border-box;width:100%;padding:14px;font:inherit;border-radius:10px;border:1px solid #a8bca6}
button{margin-top:24px;background:#245b35;color:white}p{line-height:1.5}
</style><h1>Benvenuto in Farphone</h1><p>Collega il tuo stick al Wi-Fi di casa. Usa una rete a 2,4 GHz.</p>
<p role="status">''' + message + '''</p><form method="post" action="/save">
<input type="hidden" name="token" value="''' + token + '''">
<label for="ssid">Reti Wi-Fi disponibili</label><select id="ssid" name="ssid">
<option value="">Seleziona una rete</option>''' + options + '''</select><p>''' + hint + '''</p>
<details><summary>Rete nascosta o non presente?</summary>
<label for="manual_ssid">Nome della rete Wi-Fi</label><input id="manual_ssid" name="manual_ssid" maxlength="32" autocapitalize="none" spellcheck="false">
<p>Se compilato, questo nome viene usato al posto della rete selezionata. Per aggiornare l’elenco, riapri il setup sullo stick.</p></details>
<label for="password">Password della rete</label><input id="password" name="password" type="password" maxlength="64" autocomplete="off">
<p>Lascia la password vuota solo per una rete aperta.</p>
<label for="backend_url">Indirizzo del server</label>
<input id="backend_url" name="backend_url" type="url" required maxlength="200" placeholder="http://192.168.178.45:8080" autocapitalize="none" spellcheck="false">
<p>Inserisci l’indirizzo HTTP e la porta del server, senza percorsi. Il server deve essere raggiungibile dalla rete Wi-Fi dello stick.</p>
<button>Collega lo stick</button></form>
<p>Attendi fino a 15 secondi e controlla anche lo schermo dello stick. Puoi uscire premendo A sul dispositivo.</p></html>'''


def reply(client, html, status='200 OK'):
    body = html.encode('utf-8')
    client.sendall(('HTTP/1.0 ' + status + '\r\nContent-Type: text/html; charset=utf-8\r\n'
                    'Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n'
                    "Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'\r\n"
                    'Connection: close\r\nContent-Length: ' + str(len(body)) + '\r\n\r\n').encode('utf-8'))
    client.sendall(body)


def run_setup(show, cancelled, timeout_ms=180000):
    """show(ssid, temporary_password, address, status); cancelled polls M5 buttons."""
    ap = network.WLAN(network.AP_IF)
    sta = network.WLAN(network.STA_IF)
    listener = None
    # A non-hex prefix avoids QR readers treating the passphrase as a hex key.
    password = 'Fp' + binascii.hexlify(os.urandom(6)).decode()
    token = binascii.hexlify(os.urandom(16)).decode()
    ssid = 'Farphone-' + password[-4:]
    address = '192.168.4.1'
    started = time.ticks_ms()

    def expired():
        return time.ticks_diff(time.ticks_ms(), started) >= timeout_ms

    try:
        sta.active(False)
        networks = scan_networks(sta)
        ap.active(True)
        # UIFlow/ESP32 legacy names, with the newer MicroPython aliases as fallback.
        try:
            ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA2_PSK)
        except (AttributeError, ValueError, TypeError):
            ap.config(ssid=ssid, key=password, security=3)
        ap.ifconfig((address, '255.255.255.0', address, address))
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((address, 80))
        listener.listen(1)
        listener.settimeout(0.2)
        show(ssid, password, address, 'Collega il telefono')
        while not expired() and not cancelled():
            try:
                client, _ = listener.accept()
            except OSError:
                continue
            saved = False
            try:
                client.settimeout(1)
                method, path, body = read_request(client)
                if method == 'GET' and path == '/':
                    reply(client, page(token, networks=networks))
                elif method == 'POST' and path == '/save':
                    fields = decode_form(body)
                    if fields.get('token') != token:
                        reply(client, 'Richiesta non valida.', '403 Forbidden')
                        continue
                    backend_url = validate_backend_url(fields.get('backend_url'))
                    credentials = validate(fields.get('manual_ssid') or fields.get('ssid'), fields.get('password', ''), backend_url)
                    show(ssid, password, address, 'Connessione...')
                    connected = False
                    try:
                        sta.active(False)
                        sta.active(True)
                        sta.connect(credentials['ssid'], credentials['password'])
                        attempt = time.ticks_ms()
                        while not expired() and not cancelled():
                            if sta.isconnected():
                                connected = True
                                break
                            if time.ticks_diff(time.ticks_ms(), attempt) >= 12000:
                                break
                            time.sleep_ms(100)
                        if connected:
                            save_credentials(credentials['ssid'], credentials['password'], credentials['backend_url'])
                            saved = True
                    except OSError:
                        # Do not print driver exceptions: some may contain credentials.
                        connected = False
                    finally:
                        sta.active(False)
                    if saved:
                        show(ssid, password, address, 'Wi-Fi salvato!')
                        reply(client, '<h1>Configurazione salvata!</h1><p>Wi-Fi e indirizzo del server salvati. Puoi tornare alla tua rete Wi-Fi. Lo stick tentera ora la sincronizzazione.</p>')
                    else:
                        show(ssid, password, address, 'Non salvato. Riprova')
                        reply(client, page(token, 'Connessione o salvataggio non riusciti. Controlla rete e password e riprova.', networks))
                else:
                    reply(client, 'Apri http://' + address, '404 Not Found')
            except (OSError, ValueError, TypeError):
                try:
                    reply(client, page(token, 'Richiesta non valida. Seleziona una rete o inseriscila manualmente e controlla l’indirizzo del server.', networks), '400 Bad Request')
                except OSError:
                    pass
            finally:
                client.close()
            # A phone may disconnect during the STA channel change; keep a valid save.
            if saved:
                time.sleep_ms(1200)
                return True
        return False
    finally:
        try:
            if listener:
                listener.close()
        finally:
            try:
                ap.active(False)
            finally:
                sta.active(False)
