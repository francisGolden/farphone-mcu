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
    def __init__(self, play_wav_fn=None, bright_active=80):
        self.play_wav = play_wav_fn
        self.bright_active = bright_active
        self.is_display_on = True

    def display_on(self):
        if not self.is_display_on:
            Lcd.setBrightness(self.bright_active)
            self.is_display_on = True

    def display_off(self):
        if self.is_display_on:
            Lcd.setBrightness(0)
            self.is_display_on = False

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
        Lcd.print("[B] NEXT INTENT")

    def render(self, state, seed_idx, user_name, total_points, score, focus_seconds):
        if not self.is_display_on:
            return

        if state == STATE_REVIEW:
            self.render_contract_review(seed_idx)
            return

        Lcd.clear(0x000000)
        bat = get_battery_percentage()
        bat_color = 0x00FF00 if bat > 30 else (0xFFFF00 if bat > 15 else 0xFF0000)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(bat_color, 0x000000)
        Lcd.setCursor(95, 6)
        Lcd.print(f"{bat}%")

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