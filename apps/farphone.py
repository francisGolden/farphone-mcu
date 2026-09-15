from libs.diagnostic_log import log as print
import math
import time
import random
import config
from machine import Pin
import M5
from M5 import BtnA, BtnB, Imu, Lcd, Speaker
from libs.network.network_client import initial_sync
from libs.network.wifi_credentials import load_credentials
from libs.motion_detector import SmartMotionDetector
from libs.offline_storage import get_pending_syncs
from libs.constants import STATE_IDLE, STATE_REVIEW, STATE_FOCUS, STATE_INTERRUPTED
from res.data.seeds_catalog import SEEDS_CATALOG
from libs.frontend.ui_renderer import UiRenderer
from libs.session import SessionManager
from libs.power_manager import CpuPowerManager

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

try:
    led = Pin(10, Pin.OUT)
    led.value(1)  # Active-low: 1 = OFF
except Exception:
    led = None

def led_blink(duration_ms=15):
    if led:
        led.value(0)
        time.sleep_ms(duration_ms)
        led.value(1)

def play_wav(path, volume=240):
    try:
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
        return acc[0], acc[1], acc[2]
    except Exception:
        return 0.0, 0.0, 0.0

detector = SmartMotionDetector(
    alpha=0.85,
    energy_threshold=0.22,
    sustain_ms=300,
    tilt_threshold_rad=0.22
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
    play_wav_fn=play_wav,
    render_ui_fn=ui.render,
    trigger_breach_fn=ui.trigger_breach_alert,
    render_sync_console_fn=ui.render_sync_console,
    roll_crop_fn=roll_random_crop,
    show_timing_fn=(ui.show_harvest_timing
                    if getattr(config, "HARVEST_TIMING_SCREEN", True) else None)
)

def render_current_ui():
    ui.render(
        session.current_state,
        app_state["selected_seed_idx"],
        app_state["user_name"],
        app_state["total_points"],
        session.score,
        session.focus_seconds
    )

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

local_pending = get_pending_syncs()
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
last_heartbeat_ms = time.ticks_ms()
# Separate adaptive reference: focus detection keeps its own orientation baseline.
idle_gravity = list(read_accel())
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

    # --- BTN A (Confirm / Start / Peek) ---
    if BtnA.wasPressed():
        last_activity_ms = now
        if session.current_state in (STATE_IDLE, STATE_INTERRUPTED):
            session.current_state = STATE_REVIEW
            ui.display_on()
            render_current_ui()
        elif session.current_state == STATE_REVIEW:
            session.start_session(app_state)
            last_activity_ms = session.last_activity_ms
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
        if detector.update(acc_sample):
            session.interrupt_session(app_state)
            last_activity_ms = session.last_activity_ms
            continue

        target_sec = SEEDS_CATALOG[app_state["selected_seed_idx"]]["target_sec"]

        # LED Heartbeat ogni 4 secondi
        if time.ticks_diff(now, last_heartbeat_ms) >= 4000:
            last_heartbeat_ms = now
            led_blink(15)

        # Tick timer 1s
        if time.ticks_diff(now, session.last_ui_tick) >= 1000:
            session.last_ui_tick = now
            session.focus_seconds = max(
                0, time.ticks_diff(now, session.session_start_ms) // 1000
            )

            if session.focus_seconds >= target_sec:
                session.complete_session(app_state)
                last_activity_ms = session.last_activity_ms
                continue

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

    cpu_power.pause(40, display_off=not ui.is_display_on)
