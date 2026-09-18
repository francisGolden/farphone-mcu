from libs.diagnostic_log import log as print
import math
import time
import random
import config
import M5
from M5 import BtnA, BtnB, Imu, Lcd, Speaker
from libs.network.network_client import initial_sync
from libs.network.wifi_credentials import load_credentials
from libs.motion_detector import SmartMotionDetector
from libs.offline_storage import get_pending_syncs
from libs.constants import STATE_IDLE, STATE_REVIEW, STATE_FOCUS, STATE_INTERRUPTED, STATE_HARVEST_PENDING
from res.data.seeds_catalog import SEEDS_CATALOG
from libs.frontend.ui_renderer import UiRenderer
from libs.session import SessionManager
from libs.power_manager import CpuPowerManager
from libs.battery_monitor import BatteryMonitor
from libs.harvest_led import HarvestLed
from libs.utils.get_battery_percentage import get_battery_percentage

# ==============================================================================
# 1. HARDWARE & PERIPHERALS
# ==============================================================================
M5.begin()
cpu_power = CpuPowerManager(
    light_sleep_enabled=getattr(config, "LIGHT_SLEEP_ENABLED", True)
)
# M5 initialization may start the audio peripheral before the first sound.
try:
    Speaker.end()
except Exception as exc:
    print("[Power] Speaker shutdown failed:", exc)
Lcd.setBrightness(80)
Lcd.clear(0x000000)

harvest_led = HarvestLed()

def play_wav(path, volume=240):
    try:
        stop_battery_tone()
        Speaker.begin()
        Speaker.setVolume(volume)
        Speaker.playWavFile(path)
        while Speaker.isPlaying():
            time.sleep_ms(20)
        Speaker.setVolume(0)
        time.sleep_ms(40)
        Speaker.stop()
        time.sleep_ms(20)
    except Exception as e:
        print(f"[Audio] Error {path}:", e)
    finally:
        try:
            Speaker.end()
        except Exception as exc:
            print("[Audio] Speaker shutdown failed:", exc)

def read_accel():
    try:
        acc = Imu.getAccel()
        if not all(math.isfinite(value) for value in acc[:3]):
            return None
        return acc[0], acc[1], acc[2]
    except Exception:
        return None

detector = SmartMotionDetector(
    alpha=0.95,             # Preserve more of slow acceleration changes.
    energy_threshold=0.04,  # High sensitivity with a little more noise tolerance.
    sustain_ms=100,          # Reject isolated acceleration spikes.
    tilt_threshold_rad=0.0175  # About 1 degree from the calibrated position.
)

# ==============================================================================
# 2. MANAGERS & APP STATE
# ==============================================================================
USER_ID = "1d27f428-ac94-4f9e-82d0-f2a62e6c2bea"
SCREEN_TIMEOUT_MS = 10000

app_state = {
    "user_name": "Connecting...",
    "total_points": 0,
    "selected_seed_idx": 0,
    "is_display_on": True
}

def roll_random_crop(seed_data):
    roll = random.randint(1, 100)
    target_rarity = "COM"
    if roll > 90:
        target_rarity = "LEG"
    elif roll > 60:
        target_rarity = "RAR"

    candidates = [p for p in seed_data["pool"] if p["rarity"] == target_rarity]
    return random.choice(candidates) if candidates else random.choice(seed_data["pool"])

ui = UiRenderer(play_wav_fn=play_wav, bright_active=80, power_manager=cpu_power)

session = SessionManager(
    user_id=USER_ID,
    detector=detector,
    read_accel_fn=read_accel,
    display_on_fn=ui.display_on,
    display_off_fn=ui.display_off,
    show_sync_error_fn=ui.show_sync_error,
    play_wav_fn=play_wav,
    render_ui_fn=ui.render,
    trigger_breach_fn=ui.trigger_breach_alert,
    render_sync_console_fn=ui.render_sync_console,
    roll_crop_fn=roll_random_crop,
    show_timing_fn=(ui.show_harvest_timing
                    if getattr(config, "HARVEST_TIMING_SCREEN", False) else None)
)

battery_monitor = BatteryMonitor(get_battery_percentage,
                                 threshold=getattr(config, "LOW_BATTERY_PERCENT", 15))
battery_notice_until = None
battery_tone_until = None


def render_battery_notice():
    Lcd.fillRect(0, 216, 135, 24, 0x880000)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x880000)
    Lcd.setCursor(3, 220)
    Lcd.print("LOW BATTERY")


def stop_battery_tone():
    global battery_tone_until
    if battery_tone_until is not None:
        battery_tone_until = None
        try:
            Speaker.stop()
        finally:
            Speaker.end()


def render_current_ui():
    ui.render(
        session.current_state,
        app_state["selected_seed_idx"],
        app_state["user_name"],
        app_state["total_points"],
        session.score,
        session.focus_seconds
    )

    if battery_notice_until is not None:
        render_battery_notice()

# ==============================================================================
# 3. BOOTSTRAP INITIALIZATION
# ==============================================================================
# Setup is restricted to boot, never launched by a failed focus-session sync.
saved_network = load_credentials()
configure_wifi = saved_network is None or not (
    saved_network.get('backend_url') or getattr(config, 'BACKEND_URL', '')
)
if not configure_wifi:
    ui.render_sync_console("[B] Configura Wi-Fi")
    prompt_started = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), prompt_started) < 2000:
        M5.update()
        if BtnB.wasPressed():
            configure_wifi = True
            break
        time.sleep_ms(40)

if configure_wifi:
    from libs.network.wifi_setup import run_setup
    setup_cancelled = [False]

    def cancel_wifi_setup():
        M5.update()
        if BtnA.wasPressed():
            setup_cancelled[0] = True
        elif BtnB.wasPressed():
            ui.cycle_wifi_setup()
        return setup_cancelled[0]

    try:
        run_setup(ui.render_wifi_setup, cancel_wifi_setup)
    except Exception:
        # No credential-bearing exception text in application logs.
        ui.render_sync_console("SETUP NON RIUSCITO")
        time.sleep_ms(1500)
    # Consume setup button edges before the normal app loop starts.
    M5.update()

render_current_ui()

try:
    local_pending = get_pending_syncs()
except (OSError, ValueError):
    local_pending = []
    ui.render_sync_console("STORAGE ERROR")
    time.sleep_ms(1500)
offline_accumulated = sum(item.get("score", item.get("xpEarned", 0)) for item in local_pending)

try:
    profile = initial_sync(USER_ID, ui.render_sync_console)
    print("[Boot] initial_sync result:", profile)
    if profile and isinstance(profile, dict) and profile.get("username"):
        app_state["user_name"] = profile["username"]
        app_state["total_points"] = profile["totalPoints"]
    else:
        app_state["user_name"] = "Offline"
        app_state["total_points"] = offline_accumulated
except Exception as err:
    print("[Boot] Sync failed:", err)
    app_state["user_name"] = "Offline"
    app_state["total_points"] = offline_accumulated

last_activity_ms = time.ticks_ms()
last_sensor_ok_ms = time.ticks_ms()
# Separate adaptive reference: focus detection keeps its own orientation baseline.
idle_gravity = list(read_accel() or (0.0, 0.0, 1.0))
ui.display_on()
render_current_ui()

# ==============================================================================
# 4. MAIN LOOP
# ==============================================================================
while True:
    M5.update()
    now = time.ticks_ms()
    acc_sample = read_accel()
    app_state["is_display_on"] = ui.is_display_on

    if battery_tone_until is not None and time.ticks_diff(now, battery_tone_until) >= 0:
        try:
            stop_battery_tone()
        except Exception as exc:
            print("[Battery] Audio shutdown failed:", exc)
    if battery_notice_until is not None and time.ticks_diff(now, battery_notice_until) >= 0:
        battery_notice_until = None
        if session.current_state == STATE_HARVEST_PENDING:
            ui.display_off()
        else:
            render_current_ui()
    low_battery = battery_monitor.poll(now)
    if low_battery is not None:
        battery_notice_until = time.ticks_add(now, 4000)
        ui.display_on()
        if session.current_state == STATE_HARVEST_PENDING:
            Lcd.clear(0x000000)
        render_battery_notice()
        last_activity_ms = now
        # Tone playback is asynchronous: motion detection continues every 40 ms.
        battery_tone_until = time.ticks_add(now, 180)
        try:
            Speaker.begin()
            Speaker.setVolume(80)
            Speaker.tone(1800, 120)
        except Exception as exc:
            print("[Battery] Warning tone unavailable:", exc)

    # Finish before processing input: an interaction after the deadline is no breach.
    if session.current_state == STATE_FOCUS:
        target_sec = SEEDS_CATALOG[app_state["selected_seed_idx"]]["target_sec"]
        if (acc_sample is not None and time.ticks_diff(now, last_sensor_ok_ms) < 1000
                and time.ticks_diff(now, session.session_start_ms) >= target_sec * 1000):
            session.focus_seconds = target_sec
            session.complete_session(app_state)
            last_activity_ms = session.last_activity_ms

    harvest_led.update(session.current_state == STATE_HARVEST_PENDING, now)

    if session.current_state == STATE_HARVEST_PENDING:
        # Keep the session's calibrated motion reference, including slow pickup.
        pressed = BtnA.wasPressed() or BtnB.wasPressed()
        if pressed or detector.update(acc_sample):
            try:
                stop_battery_tone()
            except Exception as exc:
                print("[Battery] Audio shutdown failed:", exc)
            battery_notice_until = None
            harvest_led.update(False, now)
            session.reveal_harvest(app_state)
            last_activity_ms = session.last_activity_ms
            idle_gravity = list(read_accel() or idle_gravity)
            M5.update()  # Consume input used to reveal the reward.
        elif battery_notice_until is not None and not ui.is_display_on:
            ui.display_on()
            render_battery_notice()
        cpu_power.pause(40, display_off=not ui.is_display_on and battery_tone_until is None)
        continue

    # --- BTN A (Confirm / Start / Peek) ---
    if BtnA.wasPressed():
        last_activity_ms = now
        if session.current_state in (STATE_IDLE, STATE_INTERRUPTED):
            session.current_state = STATE_REVIEW
            ui.display_on()
            render_current_ui()
        elif session.current_state == STATE_REVIEW:
            session.start_session(app_state)
            last_activity_ms = time.ticks_ms()
            last_sensor_ok_ms = last_activity_ms
            # Calibration/audio are blocking: discard the pre-start sample.
            now = time.ticks_ms()
            acc_sample = read_accel()
        elif session.current_state == STATE_FOCUS:
            session.record_peek(now, app_state)

    # --- BTN B (Cycle Intent / Cancel / Peek) ---
    if BtnB.wasPressed():
        last_activity_ms = now
        if session.current_state == STATE_IDLE:
            app_state["selected_seed_idx"] = (app_state["selected_seed_idx"] + 1) % len(SEEDS_CATALOG)
            ui.display_on()
            render_current_ui()
        elif session.current_state == STATE_REVIEW:
            session.current_state = STATE_IDLE
            ui.display_on()
            render_current_ui()
        elif session.current_state == STATE_FOCUS:
            session.record_peek(now, app_state)

    # --- FOCUS ACTIVE STATE ---
    if session.current_state == STATE_FOCUS:
        if acc_sample is None:
            detector.update(None)
            if time.ticks_diff(now, last_sensor_ok_ms) >= 1000:
                # A sensor failure is not a user breach and must not earn a harvest.
                session.current_state = STATE_REVIEW
                last_activity_ms = now
                ui.render_sync_console('IMU ERROR - RETRY')
            cpu_power.pause(40, display_off=not ui.is_display_on and battery_tone_until is None)
            continue
        last_sensor_ok_ms = now
        if detector.update(acc_sample):
            stop_battery_tone()
            battery_notice_until = None
            session.interrupt_session(app_state)
            last_activity_ms = session.last_activity_ms
            continue

        target_sec = SEEDS_CATALOG[app_state["selected_seed_idx"]]["target_sec"]

        # Tick timer 1s
        if time.ticks_diff(now, session.last_ui_tick) >= 1000:
            session.last_ui_tick = now
            session.focus_seconds = max(
                0, time.ticks_diff(now, session.session_start_ms) // 1000
            )

            if ui.is_display_on:
                render_current_ui()

        # Spegnimento display / timeout peek
        if ui.is_display_on:
            if session.peek_count > 0:
                display_expired = time.ticks_diff(now, session.peek_until_ms) >= 0
            else:
                display_expired = time.ticks_diff(now, last_activity_ms) > SCREEN_TIMEOUT_MS
            if display_expired:
                ui.display_off()

    # --- IDLE & REVIEW STATE (Wake-on-tilt) ---
    elif session.current_state in (STATE_IDLE, STATE_REVIEW, STATE_INTERRUPTED):
        if acc_sample is None:
            acc_sample = idle_gravity
        dx = acc_sample[0] - idle_gravity[0]
        dy = acc_sample[1] - idle_gravity[1]
        dz = acc_sample[2] - idle_gravity[2]

        # Follow the resting orientation so a fixed tilt cannot prevent timeout.
        for axis in range(3):
            idle_gravity[axis] = 0.85 * idle_gravity[axis] + 0.15 * acc_sample[axis]

        if math.sqrt(dx**2 + dy**2 + dz**2) > 0.35:
            last_activity_ms = now
            if not ui.is_display_on:
                ui.display_on()
                render_current_ui()

        if ui.is_display_on and time.ticks_diff(now, last_activity_ms) > SCREEN_TIMEOUT_MS:
            ui.display_off()

    cpu_power.pause(40, display_off=not ui.is_display_on and battery_tone_until is None)
