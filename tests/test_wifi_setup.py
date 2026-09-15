import importlib
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from libs.network import wifi_credentials as credentials


class CredentialsTests(unittest.TestCase):
    def test_round_trip_and_invalid_save_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(credentials, 'PATH', directory + '/wifi.json'):
            self.assertIsNone(credentials.load_credentials())
            credentials.save_credentials('Caffè + casa', ' a&b=%pass ')
            self.assertEqual(credentials.load_credentials()['password'], ' a&b=%pass ')
            with self.assertRaises(ValueError):
                credentials.save_credentials('é' * 17, 'pass')
            self.assertEqual(credentials.load_credentials()['ssid'], 'Caffè + casa')

    def test_url_persists_and_invalid_url_preserves_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(credentials, 'PATH', directory + '/wifi.json'):
            credentials.save_credentials('Home', 'password', ' http://server.local:8080/ ')
            self.assertEqual(credentials.load_credentials()['backend_url'], 'http://server.local:8080')
            for invalid in ('', 'https://server', 'http://server/api', 'http://user:pass@server',
                            'http://server:0', 'http://server:65536', 'http://server?x=1',
                            'http://server\r\nInjected: yes'):
                with self.subTest(url=invalid), self.assertRaises(ValueError):
                    credentials.save_credentials('Other', 'password', invalid)
                self.assertEqual(credentials.load_credentials()['ssid'], 'Home')

    def test_failed_rename_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(credentials, 'PATH', directory + '/wifi.json'):
            credentials.save_credentials('Old', 'old password')
            with patch.object(credentials.os, 'rename', side_effect=OSError('flash error')):
                with self.assertRaises(OSError):
                    credentials.save_credentials('New', 'new password')
            self.assertEqual(credentials.load_credentials()['ssid'], 'Old')


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.ap, self.sta = Mock(), Mock()
        self.sta.scan.return_value = []
        self.network = types.SimpleNamespace(AP_IF=1, STA_IF=0, AUTH_WPA2_PSK=3,
            WLAN=lambda interface: self.ap if interface else self.sta)
        with patch.dict(sys.modules, {'network': self.network}):
            sys.modules.pop('libs.network.wifi_setup', None)
            self.setup = importlib.import_module('libs.network.wifi_setup')
        self.clock = types.SimpleNamespace(ticks_ms=Mock(return_value=0),
            ticks_diff=lambda a, b: a-b, sleep_ms=Mock())
        self.setup.time = self.clock
        self.server = Mock()
        self.setup.socket = types.SimpleNamespace(socket=lambda: self.server,
            SOL_SOCKET=1, SO_REUSEADDR=2)

    def tearDown(self):
        sys.modules.pop('libs.network.wifi_setup', None)

    def test_scan_deduplicates_and_sorts_by_signal(self):
        self.sta.scan.return_value = [(b'Weak', b'', 1, -85, 3, 0),
            (b'Home', b'', 6, -70, 3, 0), (b'Home', b'', 11, -40, 3, 0),
            (b'', b'', 1, -20, 3, 1), (b'\xff', b'', 1, -20, 3, 0)]
        self.assertEqual(self.setup.scan_networks(self.sta), ['Home', 'Weak'])
        self.sta.active.assert_called_with(False)

    def test_failed_scan_keeps_manual_setup_available(self):
        self.sta.scan.side_effect = OSError('scan failed')
        self.assertEqual(self.setup.scan_networks(self.sta), [])
        self.sta.active.assert_called_with(False)
        self.assertIn('manual_ssid', self.setup.page('token'))

    def test_network_names_are_escaped_in_html(self):
        html = self.setup.page('token', networks=['<script>"&'])
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;&quot;&amp;', html)

    def test_form_unicode_and_special_password(self):
        fields = self.setup.decode_form(b'ssid=Caff%C3%A8+Casa&password=+a%26b%3D%25%2B+')
        self.assertEqual(fields, {'ssid': 'Caffè Casa', 'password': ' a&b=%+ '})

    def test_fragmented_request_and_body_limit(self):
        client = Mock()
        client.recv.side_effect = [b'POST /save HTTP/1.1\r\nContent-Length: 7\r\n', b'\r\na=', b'hello']
        self.assertEqual(self.setup.read_request(client), ('POST', '/save', b'a=hello'))
        client.recv.side_effect = [b'POST /save HTTP/1.1\r\nContent-Length: 100000\r\n\r\n']
        with self.assertRaises(ValueError):
            self.setup.read_request(client)

    def test_displayed_password_matches_ap_without_quote_wrapping(self):
        show = Mock()
        self.setup.run_setup(show, lambda: True)
        password = show.call_args.args[1]
        self.assertTrue(password.startswith('Fp'))
        self.assertEqual(len(password), 14)
        self.assertNotIn('"', password)
        self.assertEqual(self.ap.config.call_args.kwargs['password'], password)

    def test_cancel_closes_server_and_both_radios(self):
        self.assertFalse(self.setup.run_setup(Mock(), lambda: True))
        self.server.close.assert_called_once()
        self.ap.active.assert_called_with(False)
        self.sta.active.assert_called_with(False)

    def test_timeout_closes_radios(self):
        self.clock.ticks_ms.side_effect = [0, 180001]
        self.assertFalse(self.setup.run_setup(Mock(), lambda: False))
        self.ap.active.assert_called_with(False)
        self.sta.active.assert_called_with(False)

    def test_ap_failure_closes_radios(self):
        self.ap.config.side_effect = OSError('unsupported AP')
        with self.assertRaises(OSError):
            self.setup.run_setup(Mock(), lambda: False)
        self.ap.active.assert_called_with(False)
        self.sta.active.assert_called_with(False)

    def run_submission(self, connected=True, valid_token=True, manual_ssid=""):
        client = Mock()
        self.server.accept.return_value = (client, ('phone', 1))
        # First loop accepts one request; later loop cancels if not saved.
        checks = iter([False, False, True, True] if valid_token else [False, True])
        cancelled = lambda: next(checks, True)
        self.sta.isconnected.return_value = connected
        fields = {'manual_ssid': manual_ssid, 'ssid': 'Home', 'password': 'secretpass', 'backend_url': 'http://192.168.178.45:8080', 'token': '00' * 16 if valid_token else 'bad'}
        with patch.object(self.setup.os, 'urandom', side_effect=lambda n: bytes(n)), \
             patch.object(self.setup, 'read_request', return_value=('POST', '/save', b'')), \
             patch.object(self.setup, 'decode_form', return_value=fields), \
             patch.object(self.setup, 'save_credentials') as save:
            result = self.setup.run_setup(Mock(), cancelled)
        self.ap.active.assert_called_with(False)
        self.sta.active.assert_called_with(False)
        client.close.assert_called_once()
        return result, save

    def test_manual_network_overrides_selection(self):
        result, save = self.run_submission(manual_ssid='Hidden network')
        self.assertTrue(result)
        save.assert_called_once_with('Hidden network', 'secretpass', 'http://192.168.178.45:8080')

    def test_verified_credentials_are_saved(self):
        result, save = self.run_submission()
        self.assertTrue(result)
        save.assert_called_once_with('Home', 'secretpass', 'http://192.168.178.45:8080')

    def test_failed_connection_preserves_credentials(self):
        result, save = self.run_submission(connected=False)
        self.assertFalse(result)
        save.assert_not_called()

    def test_invalid_token_cannot_change_credentials(self):
        result, save = self.run_submission(valid_token=False)
        self.assertFalse(result)
        save.assert_not_called()
        self.sta.connect.assert_not_called()
