import time
import M5
from M5 import Lcd
from libs.constants import STATE_IDLE, STATE_REVIEW, STATE_FOCUS, STATE_INTERRUPTED
from res.data.seeds_catalog import SEEDS_CATALOG
from libs.frontend.pixel_art_engine import (
    draw_mystery_sprout,
    draw_withered_crop,
    draw_revealed_plant
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
                title = '1. Collega Wi-Fi'
            else:
                payload = 'http://' + address
                title = '2. Apri il setup'
            try:
                # Version 4: 33 modules at 3 pixels each, plus a 4-module quiet zone.
                Lcd.fillRect(6, 33, 123, 123, 0xFFFFFF)
                if Lcd.drawQR(payload, 18, 45, 99, 4) is False:
                    raise ValueError('QR rendering failed')
                text(title, 8, 0x00FF88)
                text('Scansiona col tel.', 164)
                text(status[:19], 182)
                text('[B] Avanti', 202)
                text('[A] Esci - 3 min', 222)
                return
            except (AttributeError, ValueError, TypeError, OSError):
                # Keep setup usable on firmware builds without the QR drawing API.
                self._wifi_qr_available = False
                Lcd.clear(0x000000)

        lines = ("CONFIGURA WI-FI", status[:19], "Rete sul telefono:", ssid,
                 "Password:", password, "Browser: http://", address,
                 "[B] QR  [A] Esci", "Scadenza: 3 minuti")
        for index, line in enumerate(lines):
            text(line, 8 + index * 22, 0x00FF88 if index == 0 else 0xFFFFFF)

    def show_harvest_timing(self, timings, synced):
        """Diagnostic screen: sync has finished and radios have been shut down."""
        self.display_on()
        M5.update()
        Lcd.clear(0x000000)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        rows = [('HARVEST TEMPI', None),
                ('Sync OK' if synced else 'Sync fallito', None),
                ('Wi-Fi', 'wifi'), ('POST', 'post'), ('GET', 'get'),
                ('Radio off', 'off'), ('Animazione', 'presentation'),
                ('Sync', 'sync'), ('Totale', 'total')]
        for index, (label, key) in enumerate(rows):
            Lcd.setCursor(3, 6 + index * 23)
            if key is None:
                Lcd.print(label)
            else:
                elapsed = timings.get(key)
                value = '--' if elapsed is None else '%.2fs' % (elapsed / 1000)
                Lcd.print(label + ': ' + value)
        Lcd.setCursor(3, 222)
        Lcd.print('[A/B] Continua')
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
        Lcd.print('[A/B] Continua')
        # Fresh input dismisses the screen; timeout limits unattended display use.
        started = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), started) < 60000:
            M5.update()
            if M5.BtnA.wasPressed() or M5.BtnB.wasPressed():
                break
            time.sleep_ms(40)

    def trigger_breach_alert(self, held_seconds=0):
        self.display_on()
        Lcd.clear(0x000000)
        draw_withered_crop(67, 65)

        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0xFF2222, 0x000000)
        Lcd.setCursor(8, 126)
        Lcd.print("CROP WITHERED")

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xAAAAAA, 0x000000)
        Lcd.setCursor(10, 154)
        Lcd.print("Contract Breached!")

        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(10, 174)
        Lcd.print(f"Held for: {held_seconds}s")

        Lcd.setTextColor(0xFF6666, 0x000000)
        Lcd.setCursor(10, 196)
        Lcd.print("Seed Lost: 0 XP")

        if self.play_wav:
            self.play_wav("res/audio/whistle.wav")
        time.sleep_ms(1500)

    def render_sync_console(self, step_text):
        self.display_on()
        Lcd.clear(0x000000)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0x00AAFF, 0x000000)
        Lcd.setCursor(10, 20)
        Lcd.print("SYNCING...")
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(10, 60)
        Lcd.print(step_text)

    def render_contract_review(self, selected_seed_idx):
        Lcd.clear(0x000000)
        seed = SEEDS_CATALOG[selected_seed_idx]

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xFFA500, 0x000000)
        Lcd.setCursor(10, 12)
        Lcd.print("INTENT PACT")
        Lcd.drawLine(8, 28, 127, 28, 0x553311)

        Lcd.setTextColor(0x888888, 0x000000)
        Lcd.setCursor(8, 38)
        Lcd.print("Seed of:")
        Lcd.setTextColor(seed["accent_color"], 0x000000)
        Lcd.setCursor(8, 54)
        Lcd.print(seed["name"])

        Lcd.setTextColor(0x888888, 0x000000)
        Lcd.setCursor(8, 76)
        Lcd.print("Pact Target:")
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(8, 92)
        mins = seed["target_sec"] // 60
        Lcd.print(f"{mins} Minutes" if mins > 0 else f"{seed['target_sec']}s")

        Lcd.setTextColor(0x888888, 0x000000)
        Lcd.setCursor(8, 114)
        Lcd.print("Possible Yield:")
        Lcd.setTextColor(0x00FF88, 0x000000)
        Lcd.setCursor(8, 130)
        Lcd.print("? Mystery Plant")

        Lcd.drawLine(8, 154, 127, 154, 0x444444)
        Lcd.setTextColor(0x00AAFF, 0x000000)
        Lcd.setCursor(6, 170)
        Lcd.print("[A] PLANT & LOCK")
        Lcd.setTextColor(0x777777, 0x000000)
        Lcd.setCursor(6, 198)
        Lcd.print("[B] BACK")

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
            Lcd.print("GREENHOUSE")

            Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
            Lcd.setTextColor(0x00AAFF, 0x000000)
            Lcd.setCursor(8, 48)
            user_disp = user_name[:9]
            Lcd.print(f"Farm: {user_disp}")
            Lcd.setCursor(8, 66)
            Lcd.print(f"Total: {total_points} XP")

            Lcd.setTextColor(0x888888, 0x000000)
            Lcd.setCursor(8, 95)
            Lcd.print("Intent Selected:")
            Lcd.setTextColor(seed["accent_color"], 0x000000)
            Lcd.setCursor(8, 112)
            Lcd.print(f"> {seed['name']} <")

            Lcd.setTextColor(0xAAAAAA, 0x000000)
            Lcd.setCursor(8, 142)
            Lcd.print("[BTN B] Change")
            Lcd.setCursor(8, 162)
            Lcd.print("[BTN A] Pact")

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
            Lcd.setTextColor(seed["accent_color"], 0x000000)
            Lcd.setCursor(14, 148)
            Lcd.print(f"Seed: {seed['name'][:9]}")

            Lcd.setTextColor(0xFFA500, 0x000000)
            Lcd.setCursor(16, 172)
            Lcd.print("PHONE LOCKED")

            Lcd.setTextColor(0x555555, 0x000000)
            Lcd.setCursor(20, 196)
            Lcd.print("DO NOT TOUCH")