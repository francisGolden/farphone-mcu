import ast
import json
from pathlib import Path
import types
from libs.network.wifi_credentials import validate_backend_url
import unittest
from unittest.mock import Mock


class HttpTransportTests(unittest.TestCase):
    def load_transport(self):
        tree = ast.parse(Path('libs/network/network_client.py').read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name in ('_parse_url', '_raw_tcp_request')]
        client = Mock()
        socket = types.SimpleNamespace(AF_INET=2, SOCK_STREAM=1,
            getaddrinfo=Mock(return_value=[(2, 1, 0, '', ('192.168.178.45', 8080))]),
            socket=Mock(return_value=client))
        ns = dict(socket=socket, config=types.SimpleNamespace(BACKEND_URL='http://192.168.178.45:8080'),
                  json=json, print=Mock(), load_credentials=lambda: None,
                  validate_backend_url=validate_backend_url,
                  time=types.SimpleNamespace(ticks_ms=lambda: 0, ticks_diff=lambda a, b: a-b))
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'transport', 'exec'), ns)
        return ns, socket, client

    def test_saved_url_overrides_legacy_config(self):
        ns, socket, client = self.load_transport()
        ns['load_credentials'] = lambda: {'backend_url': 'http://saved.example:9090'}
        self.assertEqual(ns['_parse_url'](), ('saved.example', 9090))

    def test_socket_closed_on_each_transport_failure(self):
        for operation, stage in [('connect', 'TCP connect'), ('sendall', 'HTTP send'), ('recv', 'HTTP receive')]:
            with self.subTest(operation=operation):
                ns, socket, client = self.load_transport()
                error = OSError(116, 'ETIMEDOUT')
                getattr(client, operation).side_effect = error
                with self.assertRaises(OSError):
                    ns['_raw_tcp_request']('GET', '/api/user')
                client.close.assert_called_once()
                ns['print'].assert_called_with('[HTTP] Failed at', stage, ':', error)

    def test_dns_failure_does_not_open_socket(self):
        ns, socket, client = self.load_transport()
        socket.getaddrinfo.side_effect = OSError(116, 'ETIMEDOUT')
        with self.assertRaises(OSError):
            ns['_raw_tcp_request']('GET', '/')
        socket.socket.assert_not_called()

    def test_response_parsing_and_cleanup(self):
        ns, socket, client = self.load_transport()
        client.recv.side_effect = [b'HTTP/1.0 200 OK\r\n\r\n{}', b'']
        self.assertEqual(ns['_raw_tcp_request']('GET', '/'), ('HTTP/1.0 200 OK', '{}'))
        client.close.assert_called_once()

    def test_invalid_configuration_fails_before_network_access(self):
        for url in ('', 'https://example.org'):
            ns, socket, client = self.load_transport()
            ns['config'].BACKEND_URL = url
            with self.assertRaises(ValueError):
                ns['_raw_tcp_request']('GET', '/')
            socket.getaddrinfo.assert_not_called()
