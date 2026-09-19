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
        self.now = 0
        self.sleeps = []
        def sleep_ms(duration):
            self.sleeps.append(duration)
            self.now += duration
        clock = types.SimpleNamespace(ticks_ms=lambda: self.now,
                                      ticks_diff=lambda a, b: a-b, sleep_ms=sleep_ms)
        ns = {'Lcd': lcd, 'M5': types.SimpleNamespace(Lcd=lcd), 'time': clock,
              'CHRONICLES': CHRONICLES,
              'draw_tamarix': Mock(),
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
        lcd.print.assert_any_call('Bearing the yield')

    def test_errors_and_setup_are_not_hidden_by_lore(self):
        ui, lcd = self.renderer()
        for message in ('WIFI: TIMEOUT', 'STORAGE ERROR'):
            lcd.reset_mock()
            ui.render_sync_console(message)
            printed = ''.join(call.args[0] for call in lcd.print.call_args_list)
            self.assertEqual(printed, message)
            self.assertFalse(ui._chronicle_active)

    def test_offline_sync_uses_loading_screen(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('SYNC OFFLINE (12)...')
        lcd.print.assert_any_call('Bearing memories')
        self.assertTrue(ui._chronicle_active)

    def test_recession_silences_audio_and_blacks_out_even_on_tone_failure(self):
        tree = ast.parse(Path('libs/frontend/ui_renderer.py').read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        for failure in (None, OSError('audio unavailable')):
            lcd, speaker, clock, draw = Mock(), Mock(), Mock(), Mock()
            speaker.tone.side_effect = failure
            ns = {'Lcd': lcd, 'M5': types.SimpleNamespace(Lcd=lcd, Speaker=speaker),
                  'time': clock, 'draw_recession_frame': draw,
                  'begin_output': lambda sp: sp.begin(),
                  'quiet_shutdown': lambda sp: (sp.setVolume(0), sp.stop(), sp.end())}
            exec(compile(ast.Module(body=[cls], type_ignores=[]), 'ui', 'exec'), ns)
            ui = ns['UiRenderer']()
            ui.trigger_breach_alert()
            self.assertEqual(draw.call_count, 13)
            self.assertEqual(speaker.stop.call_count, 2)
            speaker.end.assert_called_once()
            self.assertFalse(ui.is_display_on)
            lcd.setBrightness.assert_called_with(0)
            clock.sleep_ms.assert_called_with(2000)
            self.assertEqual([call.args[0] for call in lcd.print.call_args_list],
                             ['Thou hast sought', 'the mire.', 'The sap withdraws', 'into the deep.'])

    def test_boot_prompt_has_chronicle_and_configuration_action(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('[B] Wi-Fi setup')
        lcd.print.assert_any_call('CHRONICLES')
        lcd.print.assert_any_call('[B] Wi-Fi setup')

    def test_reading_time_counts_network_time(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('WIFI: CONNECTING...')
        verse = CHRONICLES[ui._chronicle_index][1]
        expected = min(14000, max(8000, 1500 + sum(len(s.split()) for s in verse) * 500))
        self.now = 3000
        ui.render_sync_console('WIFI: OFF')
        self.assertEqual(self.sleeps, [expected - 3000])

    def test_slow_network_needs_no_extra_wait(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('WIFI: CONNECTING...')
        self.now = 20000
        ui.render_sync_console('WIFI: OFF')
        self.assertEqual(self.sleeps, [])

    def test_boot_verse_survives_into_connection(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('[B] Wi-Fi setup')
        first = ui._chronicle_index
        self.now = 2000
        ui.render_sync_console('WIFI: CONNECTING...')
        self.assertEqual(ui._chronicle_index, first)
        self.assertEqual(ui._chronicle_started_ms, 0)

    def test_teardown_does_not_hide_connection_error(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('WIFI: CONNECTING...')
        ui.render_sync_console('WIFI: TIMEOUT')
        lcd.reset_mock()
        ui.render_sync_console('WIFI: OFF')
        lcd.clear.assert_not_called()
        self.assertEqual(self.sleeps, [])

    def test_progress_redraws_only_footer_and_skips_same_message(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('WIFI: CONNECTING...')
        lcd.reset_mock()
        ui.render_sync_console('WIFI OK')
        lcd.clear.assert_not_called()
        lcd.fillRect.assert_called_once_with(0, 219, 135, 21, 0x000000)
        lcd.print.assert_called_once_with('The way is open.')
        lcd.reset_mock()
        ui.render_sync_console('WIFI OK')
        lcd.clear.assert_not_called()
        lcd.fillRect.assert_not_called()
        lcd.print.assert_not_called()

    def test_new_operation_redraws_full_chronicle(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('WIFI: CONNECTING...')
        ui.render_sync_console('WIFI: OFF')
        lcd.reset_mock()
        ui.render_sync_console('WIFI: CONNECTING...')
        lcd.clear.assert_called_once()
        lcd.print.assert_any_call('CHRONICLES')

    def test_boot_does_not_draw_main_screen_before_initial_sync(self):
        tree = ast.parse(Path('apps/tamarix.py').read_text())
        sync_line = next(node.lineno for node in ast.walk(tree)
                         if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Name)
                         and node.func.id == 'initial_sync')
        main_renders = [node.lineno for node in tree.body
                        if isinstance(node, ast.Expr)
                        and isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == 'render_current_ui']
        self.assertTrue(main_renders)
        self.assertTrue(all(line > sync_line for line in main_renders))

    def test_other_screen_invalidates_partial_chronicle_redraw(self):
        ui, lcd = self.renderer()
        ui.render_sync_console('WIFI: CONNECTING...')
        ns = ui.render_contract_review.__globals__
        ns['SEEDS_CATALOG'] = [{'name': 'Rest', 'target_sec': 3600,
                               'accent_color': 0xFFFFFF}]
        ui.render_contract_review(0)
        self.assertFalse(ui._chronicle_active)
        lcd.reset_mock()
        ui.render_sync_console('SYNC PROFILE...')
        lcd.clear.assert_called_once()
        lcd.print.assert_any_call('CHRONICLES')
        lcd.print.assert_any_call('Reading the annals')
