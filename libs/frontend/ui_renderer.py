import time
from libs.diagnostic_log import log as print
import M5
from M5 import Lcd
from libs.constants import STATE_IDLE, STATE_REVIEW, STATE_FOCUS, STATE_INTERRUPTED
from res.data.seeds_catalog import SEEDS_CATALOG
from res.data.chronicles import CHRONICLES
from libs.frontend.pixel_art_engine import (
    draw_mystery_sprout,
    draw_withered_crop,
    draw_revealed_plant,
    draw_tamarix,
    draw_chronicle_divider,
    draw_recession_frame
)
from libs.utils.get_battery_percentage import get_battery_percentage

class UiRenderer:
    def __init__(self, play_wav_fn=None, bright_active=80, power_manager=None):
        self.power_manager = power_manager
        self.play_wav = play_wav_fn
        self.bright_active = bright_active
        self.is_display_on = True
        self._wifi_setup_data = None
        self._wifi_setup_page = 0
        self._wifi_qr_available = True
        self._chronicle_started_ms = None
        self._chronicle_index = -1
        self._chronicle_active = False

    def display_on(self):
        if self.power_manager:
            self.power_manager.set_idle(False)
        if not self.is_display_on:
            Lcd.setBrightness(self.bright_active)
            self.is_display_on = True

    def display_off(self):
        if self.is_display_on:
            Lcd.setBrightness(0)
            self.is_display_on = False
            if self.power_manager:
                self.power_manager.set_idle(True)

    def cycle_wifi_setup(self):
        if self._wifi_setup_data is not None:
            self._wifi_setup_page = (self._wifi_setup_page + 1) % 3
            self.render_wifi_setup(*self._wifi_setup_data)

    def render_wifi_setup(self, ssid, password, address, status):
        if self._wifi_setup_data is None or self._wifi_setup_data[:3] != (ssid, password, address):
            self._wifi_setup_page = 0
        self._wifi_setup_data = (ssid, password, address, status)
        self.display_on()
        Lcd.clear(0x000000)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)

        def text(line, y, color=0xFFFFFF):
            Lcd.setTextColor(color, 0x000000)
            Lcd.setCursor(3, y)
            Lcd.print(line)

        if self._wifi_setup_page < 2 and self._wifi_qr_available:
            # The AP name/key are generated locally. Escape reserved Wi-Fi QR characters.
            def escape(value):
                for char in ('\\', ';', ',', '"', ':'):
                    value = value.replace(char, '\\' + char)
                return value

            if self._wifi_setup_page == 0:
                payload = 'WIFI:T:WPA;S:' + escape(ssid) + ';P:' + escape(password) + ';;'
                title = '1. Join Wi-Fi'
            else:
                payload = 'http://' + address
                title = '2. Open setup'
            try:
                # Version 4: 33 modules at 3 pixels each, plus a 4-module quiet zone.
                Lcd.fillRect(6, 33, 123, 123, 0xFFFFFF)
                if Lcd.drawQR(payload, 18, 45, 99, 4) is False:
                    raise ValueError('QR rendering failed')
                text(title, 8, 0x00FF88)
                text('Scan with phone', 164)
                text(status[:19], 182)
                text('[B] Next', 202)
                text('[A] Leave - 3 min', 222)
                return
            except (AttributeError, ValueError, TypeError, OSError):
                # Keep setup usable on firmware builds without the QR drawing API.
                self._wifi_qr_available = False
                Lcd.clear(0x000000)

        lines = ("WI-FI SETUP", status[:19], "Join on thy phone:", ssid,
                 "Password:", password, "Browser: http://", address,
                 "[B] QR  [A] Leave", "Closes in 3 min")
        for index, line in enumerate(lines):
            text(line, 8 + index * 22, 0x00FF88 if index == 0 else 0xFFFFFF)

    def show_harvest_timing(self, timings, synced):
        """Diagnostic screen: sync has finished and radios have been shut down."""
        self.display_on()
        M5.update()
        Lcd.clear(0x000000)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        rows = [('HARVEST TIMES', None),
                ('Sync OK' if synced else 'Sync failed', None),
                ('Wi-Fi', 'wifi'), ('POST', 'post'), ('GET', 'get'),
                ('Radio off', 'off'), ('Animation', 'presentation'),
                ('Sync', 'sync'), ('Total', 'total')]
        for index, (label, key) in enumerate(rows):
            Lcd.setCursor(3, 6 + index * 23)
            if key is None:
                Lcd.print(label)
            else:
                elapsed = timings.get(key)
                value = '--' if elapsed is None else '%.2fs' % (elapsed / 1000)
                Lcd.print(label + ': ' + value)
        Lcd.setCursor(3, 222)
        Lcd.print('[A/B] Continue')
        while True:
            M5.update()
            if M5.BtnA.wasPressed() or M5.BtnB.wasPressed():
                break
            time.sleep_ms(40)

    def show_sync_error(self, details):
        """Retain safe diagnostics on-device without relying on USB logging."""
        self.display_on()
        M5.update()
        Lcd.clear(0x000000)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        rows = ['SAVED OFFLINE', 'Sync failed',
                details.get('error_stage', 'UNKNOWN'),
                details.get('error_code', 'NO DETAILS')]
        # Long fixed labels are wrapped for the narrow stick display.
        lines = []
        for row in rows:
            lines.extend([row[i:i+17] for i in range(0, len(row), 17)])
        for key, label in (('wifi', 'Wi-Fi'), ('post', 'POST')):
            elapsed = details.get(key)
            lines.append(label + ': ' + ('--' if elapsed is None else '%.2fs' % (elapsed / 1000)))
        for index, line in enumerate(lines):
            Lcd.setCursor(3, 8 + index * 22)
            Lcd.print(line)
        Lcd.setCursor(3, 222)
        Lcd.print('[A/B] Continue')
        # Fresh input dismisses the screen; timeout limits unattended display use.
        started = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), started) < 60000:
            M5.update()
            if M5.BtnA.wasPressed() or M5.BtnB.wasPressed():
                break
            time.sleep_ms(40)

    def trigger_breach_alert(self, held_seconds=0):
        self.display_on()

        def tone(frequency, duration):
            try:
                if M5.Speaker.tone(frequency, duration) is False:
                    print("[Recisione] Tone rejected:", frequency)
            except Exception as exc:
                print("[Recisione] Tone failed:", exc)

        try:
            try:
                M5.Speaker.begin()
                M5.Speaker.stop()
                M5.Speaker.setVolume(120)
            except Exception as exc:
                print("[Recisione] Audio initialization failed:", exc)
            # Il Gelo: one still silhouette, no alarm or flashing.
            draw_recession_frame(0)
            tone(880, 500)
            time.sleep_ms(650)
            # La Recisione: a descending tritone and rising ash.
            tone(622, 900)
            for frame in range(1, 13):
                draw_recession_frame(frame)
                time.sleep_ms(100)
            # One edict, without score, title, or reprimand.
            Lcd.clear(0x101010)
            Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
            Lcd.setTextColor(0xBBBBAF, 0x101010)
            for index, line in enumerate(("Thou hast sought", "the mire.",
                                          "The sap withdraws", "into the deep.")):
                Lcd.setCursor(5, 85 + index * 20)
                Lcd.print(line)
            time.sleep_ms(3200)
            tone(311, 40)
            time.sleep_ms(40)
        finally:
            try:
                M5.Speaker.stop()
            except Exception:
                pass
            try:
                M5.Speaker.end()
            except Exception:
                pass
        Lcd.clear(0x000000)
        self.display_off()
        time.sleep_ms(2000)

    def render_sync_console(self, step_text):
        # Teardown after an error must not hide it behind a fresh verse.
        if step_text == "WIFI: OFF" and not self._chronicle_active:
            return
        statuses = {
            "[B] Wi-Fi setup": "[B] Wi-Fi setup",
            "WIFI: CONNECTING...": "Seeking the path",
            "WIFI OK": "The way is open.",
            "SYNC HARVEST...": "Bearing the yield",
            "SYNC PROFILE...": "Reading the annals",
            "FETCHING PROFILE...": "Reading the annals",
            "WIFI: OFF": "The way is closed",
        }
        status = statuses.get(step_text)
        if step_text.startswith("SYNC OFFLINE ("):
            status = "Bearing memories"
        if status is None:
            # Setup actions and failures must remain explicit and readable.
            self._chronicle_active = False
            self.display_on()
            Lcd.clear(0x000000)
            Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
            Lcd.setTextColor(0xFFFFFF, 0x000000)
            for index in range(0, len(step_text), 17):
                Lcd.setCursor(3, 65 + (index // 17) * 20)
                Lcd.print(step_text[index:index + 17])
            return

        if not self._chronicle_active:
            self._chronicle_index = (self._chronicle_index + 1) % len(CHRONICLES)
            self._chronicle_active = True
            self._chronicle_started_ms = time.ticks_ms()
        reference, verse = CHRONICLES[self._chronicle_index]
        self.display_on()
        Lcd.clear(0x000000)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        gold, ivory = 0xB89A60, 0xDDD3BC
        for line, y in (("CHRONICLES", 9), ("OF TAMARIX", 26)):
            Lcd.setTextColor(gold, 0x000000)
            Lcd.setCursor(24, y)
            Lcd.print(line)
        draw_chronicle_divider(46)
        draw_tamarix(67, 52)
        Lcd.setTextColor(ivory, 0x000000)
        for index, line in enumerate(verse):
            Lcd.setCursor(5, 84 + index * 14)
            Lcd.print(line)
        Lcd.setTextColor(gold, 0x000000)
        Lcd.setCursor(5, 193)
        Lcd.print("Book " + reference)
        draw_chronicle_divider(213)
        Lcd.setTextColor(0x999080, 0x000000)
        Lcd.setCursor(3, 220)
        Lcd.print(status)
        if step_text == "WIFI: OFF":
            # Radios are already off. Count network time towards reading time.
            words = sum(len(line.split()) for line in verse)
            reading_ms = min(14000, max(8000, 1500 + words * 500))
            elapsed = time.ticks_diff(time.ticks_ms(), self._chronicle_started_ms)
            remaining = max(0, reading_ms - elapsed)
            if remaining:
                time.sleep_ms(remaining)
            self._chronicle_active = False

    def render_contract_review(self, selected_seed_idx):
        Lcd.clear(0x000000)
        seed = SEEDS_CATALOG[selected_seed_idx]

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xFFA500, 0x000000)
        Lcd.setCursor(10, 12)
        Lcd.print("THE PACT")
        Lcd.drawLine(8, 28, 127, 28, 0x553311)

        draw_tamarix(67, 34, scale=2)
        Lcd.setTextColor(seed["accent_color"], 0x000000)
        Lcd.setCursor(8, 101)
        Lcd.print(seed["name"])
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(8, 121)
        mins = seed["target_sec"] // 60
        Lcd.print(f"{mins} min of care" if mins > 0 else f"{seed['target_sec']}s of care")
        Lcd.setTextColor(0x888888, 0x000000)
        Lcd.setCursor(8, 143)
        Lcd.print("An unknown plant")
        draw_chronicle_divider(168)
        Lcd.setTextColor(0x00FF88, 0x000000)
        Lcd.setCursor(6, 184)
        Lcd.print("[A] Pledge thy word")
        Lcd.setTextColor(0x777777, 0x000000)
        Lcd.setCursor(6, 212)
        Lcd.print("[B] Return")

    def render(self, state, seed_idx, user_name, total_points, score, focus_seconds):
        if not self.is_display_on:
            return

        if state == STATE_REVIEW:
            self.render_contract_review(seed_idx)
            return

        Lcd.clear(0x000000)
        bat = get_battery_percentage()
        bat_color = 0x888888 if bat is None else (0x00FF00 if bat > 30 else (0xFFFF00 if bat > 15 else 0xFF0000))
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(bat_color, 0x000000)
        Lcd.setCursor(95, 6)
        Lcd.print("--%" if bat is None else f"{bat}%")

        seed = SEEDS_CATALOG[seed_idx]

        if state == STATE_IDLE:
            Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
            Lcd.setTextColor(0x00FF88, 0x000000)
            Lcd.setCursor(8, 20)
            Lcd.print("THY GARDEN")

            Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
            Lcd.setTextColor(0x00AAFF, 0x000000)
            Lcd.setCursor(8, 48)
            user_disp = user_name[:9]
            Lcd.print(f"Name: {user_disp}")
            Lcd.setCursor(8, 66)
            Lcd.print(f"Total: {total_points} XP")

            Lcd.setTextColor(0x888888, 0x000000)
            Lcd.setCursor(8, 95)
            Lcd.print("Thy chosen seed:")
            Lcd.setTextColor(seed["accent_color"], 0x000000)
            Lcd.setCursor(8, 112)
            Lcd.print(f"> {seed['name']} <")

            Lcd.setTextColor(0xAAAAAA, 0x000000)
            Lcd.setCursor(8, 142)
            Lcd.print("[B] Choose seed")
            Lcd.setCursor(8, 162)
            Lcd.print("[A] Make a pact")

            Lcd.setTextColor(0x666666, 0x000000)
            Lcd.setCursor(8, 195)
            Lcd.print(f"Last Yield: +{score}")

        elif state == STATE_FOCUS:
            target_sec = seed["target_sec"]
            remaining = max(0, target_sec - focus_seconds)
            mins = remaining // 60
            secs = remaining % 60
            progress_ratio = min(1.0, focus_seconds / target_sec)

            draw_mystery_sprout(67, 52, progress_ratio)

            Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
            Lcd.setTextColor(0xFFFFFF, 0x000000)
            Lcd.setCursor(40, 95)
            Lcd.print(f"{mins:02d}:{secs:02d}")

            bar_x, bar_y, bar_w, bar_h = 15, 125, 105, 9
            Lcd.drawRect(bar_x, bar_y, bar_w, bar_h, 0x444444)
            fill_w = int(bar_w * progress_ratio)
            if fill_w > 0:
                Lcd.fillRect(bar_x, bar_y, fill_w, bar_h, seed["accent_color"])

            Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
            lines = (
                ("[ PACT SEALED ]", 0xFFA500),
                ("Tamarix keeps", 0xFFFFFF),
                ("thy seed.", 0xFFFFFF),
                ("Disturb not", 0x888888),
                ("its rest.", 0x888888),
            )
            for index, (line, color) in enumerate(lines):
                Lcd.setTextColor(color, 0x000000)
                Lcd.setCursor(3, 145 + index * 18)
                Lcd.print(line)
