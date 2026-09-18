"""Device-local credentials; never include the generated JSON in a release."""
import json
import os

PATH = 'wifi_credentials.json'


def validate_backend_url(value):
    if not isinstance(value, str):
        raise ValueError('Enter the server HTTP address.')
    value = value.strip().rstrip('/')
    if len(value) > 200 or not value.startswith('http://'):
        raise ValueError('Use http://server-name:port (HTTPS is not supported).')
    authority = value[7:]
    if not authority or any(c in authority for c in '/?#@\\') or any(ord(c) <= 32 or ord(c) >= 127 for c in authority):
        raise ValueError('Enter only address and port, without a path or credentials.')
    parts = authority.split(':')
    host = parts[0]
    if len(parts) > 2 or not host or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in host):
        raise ValueError('Invalid server name.')
    if len(parts) == 2 and (not parts[1].isdigit() or not 1 <= int(parts[1]) <= 65535):
        raise ValueError('Invalid port.')
    return value


def validate(ssid, password, backend_url=None):
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode('utf-8')) <= 32:
        raise ValueError('The network name must contain 1 to 32 bytes.')
    if not isinstance(password, str) or len(password.encode('utf-8')) > 64:
        raise ValueError('Invalid password.')
    result = {'ssid': ssid, 'password': password}
    if backend_url is not None:
        result['backend_url'] = validate_backend_url(backend_url)
    return result


def load_credentials():
    try:
        with open(PATH) as source:
            data = json.load(source)
        return validate(data['ssid'], data['password'], data.get('backend_url'))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_credentials(ssid, password, backend_url=None):
    data = validate(ssid, password, backend_url)
    # Same-filesystem rename preserves the previous file if writing fails.
    with open(PATH + '.tmp', 'w') as target:
        json.dump(data, target)
        target.flush()
    os.rename(PATH + '.tmp', PATH)
