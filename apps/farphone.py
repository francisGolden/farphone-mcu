import math
import time
import machine
from machine import Pin
import M5
from M5 import BtnA, BtnB, Imu, Lcd, Power, Speaker
from libs.network_client import get_user_profile, update_user_points
from libs.motion_detector import SmartMotionDetector

# ==============================================================================
# 1. HARDWARE & POWER TUNING
# ==============================================================================
M5.begin()
Lcd.setBrightness(80)
Lcd.clear(0x000000)

try:
    led = Pin(10, Pin.OUT)
    led.value(1)  # 1 = SPENTO (active-low)
except Exception:
    led = None

def led_blink(duration_ms=15):
    if led:
        led.value(0)
        time.sleep_ms(duration_ms)
        led.value(1)

BRIGHT_ACTIVE = 80
BRIGHT_OFF = 0
SCREEN_TIMEOUT_MS = 10000     # 10 secondi prima dello spegnimento
PEEK_DURATION_MS = 5000       # 5 secondi con BtnA o BtnB
CALIBRATION_SETTLE_MS = 600

is_display_on = True
peek_until_ms = 0

def display_on():
    global is_display_on
    if not is_display_on:
        Lcd.setBrightness(BRIGHT_ACTIVE)
        is_display_on = True

def display_off():
    global is_display_on
    if is_display_on:
        Lcd.setBrightness(BRIGHT_OFF)
        is_display_on = False

detector = SmartMotionDetector(
    alpha=0.85,
    energy_threshold=0.22,
    sustain_ms=300,
    tilt_threshold_rad=0.22
)

# ==============================================================================
# 2. STATO, CONFIGURAZIONE & GAMIFICATION
# ==============================================================================
USER_ID = "1d27f428-ac94-4f9e-82d0-f2a62e6c2bea"
user_name = "Connecting..."
total_points = 0

STATE_IDLE = "IDLE"
STATE_FOCUS = "FOCUS"
STATE_INTERRUPTED = "INTERRUPTED"

MODES = [
    {"label": "FREE",   "target_sec": 0,       "bonus": 0},
    {"label": "1 MIN",  "target_sec": 60,      "bonus": 100},
    {"label": "30 MIN", "target_sec": 30 * 60, "bonus": 1000},
    {"label": "60 MIN", "target_sec": 60 * 60, "bonus": 2500}
]
selected_mode_idx = 0

current_state = STATE_IDLE
session_start_ms = 0
focus_seconds = 0
score = 0

last_ui_tick = time.ticks_ms()
last_heartbeat_ms = time.ticks_ms()
last_activity_ms = time.ticks_ms()

def get_battery_percentage():
    try:
        level = Power.getBatteryLevel()
        return level if level is not None else 100
    except Exception:
        return 100

def read_accel():
    try:
        acc = Imu.getAccel()
        return acc[0], acc[1], acc[2]
    except Exception:
        return 0.0, 0.0, 0.0

# ==============================================================================
# 3. GRAFICA & AUDIO
# ==============================================================================
def draw_pingu_face():
    Lcd.clear(0x000000)
    Lcd.fillCircle(67, 80, 42, 0x111111)
    Lcd.fillCircle(54, 66, 10, 0xFFFFFF)
    Lcd.fillCircle(80, 66, 10, 0xFFFFFF)
    Lcd.fillCircle(56, 66, 4, 0x000000)
    Lcd.fillCircle(78, 66, 4, 0x000000)
    Lcd.fillCircle(67, 92, 14, 0xFFA500)
    Lcd.fillCircle(67, 92, 8, 0x880000)

    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0xFF0000, 0x000000)
    Lcd.setCursor(12, 145)
    Lcd.print("NOOT NOOT!")

    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(20, 180)
    Lcd.print("PHONE MOVED!")
    Lcd.setCursor(18, 202)
    Lcd.print("Points Lost: 0")

def trigger_pingu_alert():
    display_on()
    draw_pingu_face()
    try:
        Speaker.begin()
        Speaker.setVolume(240)
        Speaker.playWavFile("res/audio/pingu.wav")
        while Speaker.isPlaying():
            time.sleep_ms(20)
        Speaker.stop()
        Speaker.end()
    except Exception as e:
        print("[Audio] Playback error:", e)
    time.sleep_ms(1500)

def render_sync_console(step_text):
    display_on()
    Lcd.clear(0x000000)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0x00AAFF, 0x000000)
    Lcd.setCursor(10, 20)
    Lcd.print("SYNCING...")
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(10, 60)
    Lcd.print(step_text)

def render_ui():
    if not is_display_on:
        return

    Lcd.clear(0x000000)
    bat = get_battery_percentage()
    bat_color = 0x00FF00 if bat > 30 else (0xFFFF00 if bat > 15 else 0xFF0000)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(bat_color, 0x000000)
    Lcd.setCursor(95, 8)
    Lcd.print(f"{bat}%")

    mode = MODES[selected_mode_idx]

    if current_state == STATE_IDLE:
        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0x00AAFF, 0x000000)
        Lcd.setCursor(8, 25)
        Lcd.print("STANDBY")

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0x00FFCC, 0x000000)
        Lcd.setCursor(8, 52)
        Lcd.print(f"User: {user_name}")
        Lcd.setCursor(8, 70)
        Lcd.print(f"Total: {total_points} pt")

        Lcd.setTextColor(0xFFFF00, 0x000000)
        Lcd.setCursor(8, 100)
        Lcd.print(f"Mode: > {mode['label']} <")

        Lcd.setTextColor(0xAAAAAA, 0x000000)
        Lcd.setCursor(8, 130)
        Lcd.print("[BTN B] Mode")
        Lcd.setCursor(8, 150)
        Lcd.print("[BTN A] Start")

        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(8, 185)
        Lcd.print(f"Last: {focus_seconds}s | +{score}")

    elif current_state == STATE_FOCUS:
        target_sec = mode["target_sec"]
        
        if target_sec > 0:
            remaining = max(0, target_sec - focus_seconds)
            mins = remaining // 60
            secs = remaining % 60
            title_text = "REMAINING"
        else:
            mins = focus_seconds // 60
            secs = focus_seconds % 60
            title_text = "FOCUS"

        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0x00FF00, 0x000000)
        Lcd.setCursor(8, 30)
        Lcd.print(title_text)

        Lcd.setFont(M5.Lcd.FONTS.DejaVu24)
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(8, 75)
        Lcd.print(f"{mins:02d}:{secs:02d}")

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0x00FF88, 0x000000)
        Lcd.setCursor(8, 125)
        Lcd.print(f"Score: {score}")
        if mode["bonus"] > 0:
            Lcd.setTextColor(0xFFFF00, 0x000000)
            Lcd.setCursor(8, 145)
            Lcd.print(f"Goal: +{mode['bonus']}pt")

        Lcd.setTextColor(0x777777, 0x000000)
        Lcd.setCursor(8, 195)
        Lcd.print("DON'T TOUCH")

# ==============================================================================
# 4. GESTIONE TRANSIZIONI SESSIONE
# ==============================================================================
def start_session():
    global current_state, session_start_ms, focus_seconds, score, last_ui_tick, last_activity_ms
    
    display_on()
    time.sleep_ms(CALIBRATION_SETTLE_MS)
    detector.reset_reference(read_accel())

    focus_seconds = 0
    score = 0
    now = time.ticks_ms()
    session_start_ms = now
    last_ui_tick = now
    last_activity_ms = now
    current_state = STATE_FOCUS
    render_ui()

def interrupt_session():
    global current_state, last_activity_ms, score, total_points
    current_state = STATE_INTERRUPTED
    
    target_sec = MODES[selected_mode_idx]["target_sec"]
    if target_sec > 0 and focus_seconds < target_sec:
        score = 0
        
    trigger_pingu_alert()
    
    if score > 0:
        try:
            if update_user_points(USER_ID, score, log_cb=render_sync_console):
                total_points += score
        except Exception as e:
            print("[Sync] Update points error:", e)

    current_state = STATE_IDLE
    last_activity_ms = time.ticks_ms()
    display_on()
    render_ui()

def complete_session():
    global current_state, last_activity_ms, score, total_points
    current_state = STATE_IDLE
    display_on()
    
    score += MODES[selected_mode_idx]["bonus"]

    Lcd.clear(0x000000)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0x00FF00, 0x000000)
    Lcd.setCursor(10, 45)
    Lcd.print("GOAL REACHED!")
    
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(10, 85)
    Lcd.print(f"Total: +{score} pts")
    Lcd.setCursor(10, 110)
    Lcd.print("Great work!")
    time.sleep_ms(2500)

    try:
        if update_user_points(USER_ID, score, log_cb=render_sync_console):
            total_points += score
    except Exception as e:
        print("[Sync] Update points error:", e)

    last_activity_ms = time.ticks_ms()
    render_ui()

# ==============================================================================
# 5. INITIAL BOOTSTRAP & PROFILAZIONE
# ==============================================================================
render_ui()

try:
    profile = get_user_profile(USER_ID, log_cb=render_sync_console)
    if profile:
        user_name = profile.get("username", "User")
        total_points = profile.get("totalPoints", 0)
    else:
        user_name = "Offline"
except Exception as err:
    print("[Boot] Fetch error:", err)
    user_name = "Offline"

last_activity_ms = time.ticks_ms()
display_on()
render_ui()

# ==============================================================================
# 6. MAIN LOOP
# ==============================================================================
while True:
    M5.update()
    now = time.ticks_ms()
    acc_sample = read_accel()

    # --- TASTO A (Start in Standby / Peek in Focus) ---
    if BtnA.wasPressed():
        last_activity_ms = now
        if current_state in (STATE_IDLE, STATE_INTERRUPTED):
            start_session()
        elif current_state == STATE_FOCUS:
            peek_until_ms = time.ticks_add(now, PEEK_DURATION_MS)
            if not is_display_on:
                display_on()
                render_ui()

    # --- TASTO B (Cambio modalità in Standby / Peek in Focus) ---
    if BtnB.wasPressed():
        last_activity_ms = now
        if current_state == STATE_IDLE:
            selected_mode_idx = (selected_mode_idx + 1) % len(MODES)
            display_on()
            render_ui()
        elif current_state == STATE_FOCUS:
            peek_until_ms = time.ticks_add(now, PEEK_DURATION_MS)
            if not is_display_on:
                display_on()
                render_ui()

    # --- STATO FOCUS ---
    if current_state == STATE_FOCUS:
        if detector.update(acc_sample):
            interrupt_session()
            continue

        target_sec = MODES[selected_mode_idx]["target_sec"]

        # LED Heartbeat ogni 4s
        if time.ticks_diff(now, last_heartbeat_ms) >= 4000:
            last_heartbeat_ms = now
            led_blink(15)

        # Tick 1s
        if time.ticks_diff(now, last_ui_tick) >= 1000:
            last_ui_tick = now
            focus_seconds += 1
            score += 2
            
            if target_sec == 0 and focus_seconds % 60 == 0:
                score += 50

            if target_sec > 0 and focus_seconds >= target_sec:
                complete_session()
                continue

            if is_display_on:
                render_ui()

        # Timeout spegnimento display
        if is_display_on:
            is_peeking = time.ticks_diff(peek_until_ms, now) > 0
            if not is_peeking and time.ticks_diff(now, last_activity_ms) > SCREEN_TIMEOUT_MS:
                display_off()

    # --- STATO IDLE ---
    elif current_state == STATE_IDLE:
        dx = acc_sample[0] - detector.gravity[0]
        dy = acc_sample[1] - detector.gravity[1]
        dz = acc_sample[2] - detector.gravity[2]
        
        if math.sqrt(dx**2 + dy**2 + dz**2) > 0.35:
            last_activity_ms = now
            if not is_display_on:
                display_on()
                render_ui()

        if is_display_on and time.ticks_diff(now, last_activity_ms) > SCREEN_TIMEOUT_MS:
            display_off()

    time.sleep_ms(40)