import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock


class WifiQrTests(unittest.TestCase):
    def renderer(self):
        tree = ast.parse(Path('libs/frontend/ui_renderer.py').read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        lcd = Mock()
        lcd.drawQR.return_value = None
        ns = {'Lcd': lcd, 'M5': types.SimpleNamespace(Lcd=lcd)}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'ui', 'exec'), ns)
        return ns['UiRenderer'](), lcd

    def test_wifi_url_and_manual_pages(self):
        ui, lcd = self.renderer()
        args = ('Tamarix-ab12', 'Tm01234567ab12', '192.168.4.1', 'Collega il telefono')
        ui.render_wifi_setup(*args)
        lcd.drawQR.assert_called_with('WIFI:T:WPA;S:Tamarix-ab12;P:Tm01234567ab12;;', 18, 45, 99, 4)
        ui.cycle_wifi_setup()
        lcd.drawQR.assert_called_with('http://192.168.4.1', 18, 45, 99, 4)
        ui.cycle_wifi_setup()
        self.assertEqual(lcd.drawQR.call_count, 2)
        lcd.print.assert_any_call('Tm01234567ab12')
        ui.cycle_wifi_setup()
        self.assertEqual(lcd.drawQR.call_count, 3)

    def test_status_update_preserves_page(self):
        ui, lcd = self.renderer()
        ui.render_wifi_setup('Tamarix-ab12', 'Tm01234567ab12', '192.168.4.1', 'Ready')
        ui.cycle_wifi_setup()
        ui.render_wifi_setup('Tamarix-ab12', 'Tm01234567ab12', '192.168.4.1', 'Connessione...')
        lcd.drawQR.assert_called_with('http://192.168.4.1', 18, 45, 99, 4)

    def test_qr_failure_falls_back_to_manual(self):
        for failure in (False, AttributeError('missing')):
            ui, lcd = self.renderer()
            if failure is False:
                lcd.drawQR.return_value = False
            else:
                lcd.drawQR.side_effect = failure
            ui.render_wifi_setup('Tamarix-ab12', 'Tm01234567ab12', '192.168.4.1', 'Ready')
            lcd.print.assert_any_call('Tm01234567ab12')
            ui.cycle_wifi_setup()
            self.assertEqual(lcd.drawQR.call_count, 1)

    def test_reserved_characters_are_escaped(self):
        ui, lcd = self.renderer()
        ui.render_wifi_setup('a;b', 'a:b', '192.168.4.1', 'Ready')
        self.assertEqual(lcd.drawQR.call_args.args[0], 'WIFI:T:WPA;S:a\\;b;P:a\\:b;;')
