import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock
from res.data.chronicles import CHRONICLES


class ChroniclesTests(unittest.TestCase):
    def renderer(self):
        tree = ast.parse(Path('libs/frontend/ui_renderer.py').read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        lcd = Mock()
        ns = {'Lcd': lcd, 'M5': types.SimpleNamespace(Lcd=lcd),
              'CHRONICLES': CHRONICLES,
              'draw_chronicle_emblem': Mock(),
              'draw_chronicle_divider': Mock()}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'ui', 'exec'), ns)
        return ns['UiRenderer'](), lcd

    def test_verse_stays_through_sync_and_rotates_next_time(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('WIFI: CONNECTING...')
        first = ui._chronicle_index
        for phase in ('WIFI OK', 'SYNC HARVEST...', 'SYNC PROFILE...', 'WIFI: OFF'):
            ui.render_sync_console(phase)
            self.assertEqual(ui._chronicle_index, first)
        ui.render_sync_console('WIFI: CONNECTING...')
        self.assertNotEqual(ui._chronicle_index, first)
        lcd.print.assert_any_call('Affido il raccolto')

    def test_errors_and_setup_are_not_hidden_by_lore(self):
        ui, lcd = self.renderer()
        for message in ('WIFI: TIMEOUT', 'STORAGE ERROR', '[B] Configura Wi-Fi'):
            lcd.reset_mock()
            ui.render_sync_console(message)
            printed = ''.join(call.args[0] for call in lcd.print.call_args_list)
            self.assertEqual(printed, message)
            self.assertFalse(ui._chronicle_active)

    def test_offline_sync_uses_loading_screen(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('SYNC OFFLINE (12)...')
        lcd.print.assert_any_call('Reco le memorie...')
        self.assertTrue(ui._chronicle_active)
