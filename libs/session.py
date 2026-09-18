from libs.diagnostic_log import log as print
import time
import M5
from M5 import Lcd
from libs.constants import STATE_IDLE, STATE_FOCUS, STATE_INTERRUPTED, STATE_HARVEST_PENDING
from res.data.seeds_catalog import SEEDS_CATALOG
from libs.offline_storage import queue_session
from libs.network.network_client import sync_session_event
from libs.frontend.pixel_art_engine import (
    draw_mystery_sprout,
    draw_revealed_plant
)

class SessionManager:
    def __init__(self, user_id, detector, read_accel_fn, display_on_fn, play_wav_fn, 
                 render_ui_fn, trigger_breach_fn, render_sync_console_fn, roll_crop_fn,
                 show_timing_fn=None, display_off_fn=None, show_sync_error_fn=None):
        self.show_sync_error = show_sync_error_fn
        self.display_off = display_off_fn
        self.pending_harvest = None
        self.show_timing = show_timing_fn
        self.user_id = user_id
        self.detector = detector
        self.read_accel = read_accel_fn
        self.display_on = display_on_fn
        self.play_wav = play_wav_fn
        self.render_ui = render_ui_fn
        self.trigger_breach_alert = trigger_breach_fn
        self.render_sync_console = render_sync_console_fn
        self.roll_crop = roll_crop_fn

        # State vars
        self.current_state = STATE_IDLE
        self.session_start_ms = 0
        self.focus_seconds = 0
        self.score = 0
        self.last_ui_tick = 0
        self.last_activity_ms = 0
        self.peek_until_ms = 0

        # EMA metrics
        self.peek_count = 0
        self.first_peek_sec = None

        # Parametri timing
        self.PEEK_DURATION_MS = 5000
        self.CALIBRATION_SETTLE_MS = 600

    def _queue_outcome(self, score, seed, plant, outcome, duration):
        try:
            return queue_session(score, seed, plant, outcome, duration,
                                 self.peek_count, self.first_peek_sec)
        except (OSError, ValueError) as exc:
            print('[Storage] Session could not be saved:', exc)
            self.render_sync_console('STORAGE ERROR')
            time.sleep_ms(1500)
            return None

    def record_peek(self, now_ms, app_state):
        """Traccia le interazioni discrete (sbirciate) durante la sessione di blocco."""
        self.peek_until_ms = time.ticks_add(now_ms, self.PEEK_DURATION_MS)
        self.peek_count += 1
        if self.first_peek_sec is None:
            self.first_peek_sec = max(0, time.ticks_diff(now_ms, self.session_start_ms) // 1000)

        if not app_state["is_display_on"]:
            self.display_on()
            app_state["is_display_on"] = True
            self.render_ui(
                self.current_state,
                app_state["selected_seed_idx"],
                app_state["user_name"],
                app_state["total_points"],
                self.score,
                self.focus_seconds
            )

    def start_session(self, app_state):
        self.display_on()
        app_state["is_display_on"] = True

        self.play_wav("res/audio/seeds.wav")
        time.sleep_ms(self.CALIBRATION_SETTLE_MS)
        sample = self.read_accel()
        if sample is None:
            self.render_sync_console('IMU ERROR - RETRY')
            return
        try:
            self.detector.reset_reference(sample)
        except ValueError:
            self.render_sync_console('IMU ERROR - RETRY')
            return

        self.focus_seconds = 0
        self.score = 0
        self.peek_count = 0
        self.first_peek_sec = None

        now = time.ticks_ms()
        self.session_start_ms = now
        self.last_ui_tick = now
        self.last_activity_ms = now
        self.current_state = STATE_FOCUS

        self.render_ui(
            self.current_state,
            app_state["selected_seed_idx"],
            app_state["user_name"],
            app_state["total_points"],
            self.score,
            self.focus_seconds
        )

    def interrupt_session(self, app_state):
        """Gestisce il movimento non consentito, allarme ed evento FAILED via telemetria."""
        self.current_state = STATE_INTERRUPTED
        self.score = 0

        elapsed_sec = max(0, time.ticks_diff(time.ticks_ms(), self.session_start_ms) // 1000)
        seed = SEEDS_CATALOG[app_state["selected_seed_idx"]]

        event_id = self._queue_outcome(0, seed['id'], None, 'FAILED', elapsed_sec)
        self.trigger_breach_alert(held_seconds=elapsed_sec)

        synced = False
        try:
            synced = event_id is not None and sync_session_event(
                self.user_id,
                seed_identifier=seed["id"],
                plant_identifier=None,
                xp_earned=0,
                harvestOutcome="FAILED",
                duration_seconds=elapsed_sec,
                peek_count=self.peek_count,
                first_peek_sec=self.first_peek_sec,
                log_cb=self.render_sync_console,
                event_id=event_id
            )
        except Exception as e:
            print("[Breach Sync] Error:", e)

        if not synced:
            self.render_sync_console('SAVED OFFLINE' if event_id else 'STORAGE ERROR')
            time.sleep_ms(1000)

        self.current_state = STATE_IDLE
        self.last_activity_ms = time.ticks_ms()
        self.display_on()
        app_state["is_display_on"] = True
        self.render_ui(
            self.current_state,
            app_state["selected_seed_idx"],
            app_state["user_name"],
            app_state["total_points"],
            self.score,
            self.focus_seconds
        )

    def complete_session(self, app_state):
        """Persist the reward silently; presentation waits for user interaction."""
        if self.pending_harvest is not None:
            return
        seed = SEEDS_CATALOG[app_state["selected_seed_idx"]]
        duration_sec = seed["target_sec"]

        picked_crop = self.roll_crop(seed)
        self.score = int(seed["bonus_base"] * picked_crop["xp_mul"])

        # Persist before audio, animations or network access can interrupt completion.
        event_id = self._queue_outcome(self.score, seed['id'], picked_crop['id'],
                                       'SUCCESSFUL', duration_sec)
        if event_id is None:
            self.current_state = STATE_IDLE
            self.score = 0
            self.last_activity_ms = time.ticks_ms()
            return

        app_state["total_points"] += self.score
        self.pending_harvest = (seed, picked_crop, event_id)
        self.current_state = STATE_HARVEST_PENDING
        self.last_activity_ms = time.ticks_ms()
        if self.display_off:
            self.display_off()
        app_state["is_display_on"] = False

    def reveal_harvest(self, app_state):
        if self.pending_harvest is None:
            return
        seed, picked_crop, event_id = self.pending_harvest
        self.pending_harvest = None
        duration_sec = seed["target_sec"]
        harvest_started = time.ticks_ms()
        self.current_state = STATE_IDLE
        self.display_on()
        app_state["is_display_on"] = True

        rarity_badge = {
            "COM": ("COMMON",    0x00FF88),
            "RAR": ("RARE",      0x00AAFF),
            "LEG": ("LEGENDARY", 0xFFA500)
        }[picked_crop["rarity"]]

        # Sequenza visuale di sblocco
        Lcd.clear(0x000000)
        draw_mystery_sprout(67, 60, 1.0)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        lines = ("[ PATTO ONORATO ]", "Il Guardiano", "delle Semenze",
                 "t'ha fatto dono", "del raccolto.")
        for index, line in enumerate(lines):
            Lcd.setTextColor(0x00FF88 if index == 0 else 0xFFFFFF, 0x000000)
            Lcd.setCursor(3, 120 + index * 20)
            Lcd.print(line)
        self.play_wav("res/audio/harvest.wav")
        time.sleep_ms(3000)

        Lcd.clear(0x000000)
        draw_revealed_plant(67, 55, rarity_badge[1])

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(rarity_badge[1], 0x000000)
        Lcd.setCursor(12, 115)
        Lcd.print(f"[{rarity_badge[0]}]")

        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(10, 136)
        Lcd.print(picked_crop["name"][:10])

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xFFFF00, 0x000000)
        Lcd.setCursor(12, 168)
        Lcd.print(f"+{self.score} XP")

        self.play_wav("res/audio/reward.wav")
        time.sleep_ms(1500)

        print("[Timing] Harvest presentation:", time.ticks_diff(time.ticks_ms(), harvest_started), "ms")
        presentation_ms = time.ticks_diff(time.ticks_ms(), harvest_started)
        timings = {}
        sync_started = time.ticks_ms()
        # Invio telemetria HTTP
        synced = False
        try:
            fresh_profile = sync_session_event(
                self.user_id,
                seed_identifier=seed["id"],
                plant_identifier=picked_crop["id"],
                xp_earned=self.score,
                harvestOutcome="SUCCESSFUL",
                duration_seconds=duration_sec,
                peek_count=self.peek_count,
                first_peek_sec=self.first_peek_sec,
                log_cb=self.render_sync_console,
                timings=timings,
                event_id=event_id
            )
            if fresh_profile and isinstance(fresh_profile, dict):
                synced = True
                app_state["user_name"] = fresh_profile.get("username", app_state["user_name"])
                app_state["total_points"] = fresh_profile.get("totalPoints", app_state["total_points"])
                print(f"[Sync] Profile refreshed: {app_state['user_name']}, Total: {app_state['total_points']} XP")
            elif fresh_profile is True:
                synced = True
        except Exception as e:
            timings['error_stage'] = 'SYNC CALL'
            timings['error_code'] = type(e).__name__
            print("[Sync] Network error:", e)

        if not synced:
            if self.show_sync_error:
                self.show_sync_error(timings)
            else:
                self.render_sync_console('SAVED OFFLINE')
                time.sleep_ms(1000)

        timings['presentation'] = presentation_ms
        timings['sync'] = time.ticks_diff(time.ticks_ms(), sync_started)
        timings['total'] = time.ticks_diff(time.ticks_ms(), harvest_started)
        if self.show_timing and (synced or not self.show_sync_error):
            self.show_timing(timings, synced)

        print("[Timing] Harvest sync and fallback:", timings["sync"], "ms")
        print("[Timing] Harvest total:", timings["total"], "ms")
        self.last_activity_ms = time.ticks_ms()
        self.render_ui(
            self.current_state,
            app_state["selected_seed_idx"],
            app_state["user_name"],
            app_state["total_points"],
            self.score,
            self.focus_seconds
        )
