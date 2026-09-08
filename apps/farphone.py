import math
import time
import M5
from M5 import BtnA, BtnB, Imu, Lcd, Power, Speaker
from machine import Pin
from libs.network_client import sync_session

# ==============================================================================
# 1. HARDWARE & LED HEARTBEAT
# ==============================================================================
M5.begin()
Speaker.begin()
Speaker.setVolume(255)

try:
    led = Pin(10, Pin.OUT)
    led.value(1)  # 1 = SPENTO (active low su ESP32 M5Stick)
except Exception:
    led = None

def led_blink(duration_ms=15):
    if led:
        led.value(0)
        time.sleep_ms(duration_ms)
        led.value(1)

# ==============================================================================
# 2. GESTIONE DISPLAY POWER
# ==============================================================================
BRIGHT_ACTIVE = 80
SCREEN_TIMEOUT_MS = 15000     # Aumentato a 15 secondi per dare tempo di leggere
PEEK_DURATION_MS = 6000       # 6 secondi quando premi BtnB
CALIBRATION_SETTLE_MS = 600

is_display_on = True
peek_until_ms = 0

def display_on():
    global is_display_on
    if not is_display_on:
        try:
            Lcd.wakeup()
        except AttributeError:
            pass
        Lcd.setBrightness(BRIGHT_ACTIVE)
        is_display_on = True

def display_off():
    global is_display_on
    if is_display_on:
        Lcd.setBrightness(0)
        try:
            Lcd.sleep()
        except AttributeError:
            pass
        is_display_on = False

display_on()

# ==============================================================================
# 3. FILTRO CINEMATICO INTELLIGENTE
# ==============================================================================
class SmartMotionDetector:
    def __init__(self, alpha=0.85, energy_threshold=0.22, sustain_ms=300, tilt_threshold_rad=0.22):
        self.alpha = alpha
        self.energy_threshold = energy_threshold
        self.sustain_ms = sustain_ms
        self.tilt_threshold = tilt_threshold_rad
        self.gravity = [0.0, 0.0, 1.0]
        self.ref_gravity = [0.0, 0.0, 1.0]
        self.motion_start_ms = None

    def reset_reference(self, initial_accel):
        ax, ay, az = initial_accel
        norm = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
        self.gravity = [ax / norm, ay / norm, az / norm]
        self.ref_gravity = list(self.gravity)
        self.motion_start_ms = None

    def update(self, raw_accel):
        now = time.ticks_ms()
        ax, ay, az = raw_accel

        self.gravity[0] = self.alpha * self.gravity[0] + (1.0 - self.alpha) * ax
        self.gravity[1] = self.alpha * self.gravity[1] + (1.0 - self.alpha) * ay
        self.gravity[2] = self.alpha * self.gravity[2] + (1.0 - self.alpha) * az

        lx = ax - self.gravity[0]
        ly = ay - self.gravity[1]
        lz = az - self.gravity[2]
        dyn_energy = math.sqrt(lx**2 + ly**2 + lz**2)

        g_norm = math.sqrt(self.gravity[0]**2 + self.gravity[1]**2 + self.gravity[2]**2) or 1.0
        dot = (self.gravity[0] * self.ref_gravity[0] +
               self.gravity[1] * self.ref_gravity[1] +
               self.gravity[2] * self.ref_gravity[2]) / g_norm
        dot = max(-1.0, min(1.0, dot))
        tilt = math.acos(dot)

        if tilt > self.tilt_threshold:
            return True

        if dyn_energy > self.energy_threshold:
            if self.motion_start_ms is None:
                self.motion_start_ms = now
            elif time.ticks_diff(now, self.motion_start_ms) >= self.sustain_ms:
                return True
        else:
            self.motion_start_ms = None

        return False

detector = SmartMotionDetector()

# ==============================================================================
# 4. STATO E GRAFICA
# ==============================================================================
STATE_IDLE = "IDLE"
STATE_FOCUS = "FOCUS"
STATE_INTERRUPTED = "INTERRUPTED"

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
    Lcd.setCursor(26, 202)
    Lcd.print("Session Ended")

def trigger_pingu_alert():
    display_on()
    draw_pingu_face()
    try:
        Speaker.setVolume(240)
        Speaker.playWavFile("res/audio/pingu.wav")
        while Speaker.isPlaying():
            time.sleep_ms(20)
        Speaker.setVolume(0)
        Speaker.stop()
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
    """Ridisegna completamente la dashboard."""
    if not is_display_on:
        return

    Lcd.clear(0x000000)
    bat = get_battery_percentage()
    bat_color = 0x00FF00 if bat > 30 else (0xFFFF00 if bat > 15 else 0xFF0000)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(bat_color, 0x000000)
    Lcd.setCursor(95, 8)
    Lcd.print(f"{bat}%")

    if current_state == STATE_IDLE:
        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0x00AAFF, 0x000000)
        Lcd.setCursor(10, 32)
        Lcd.print("STANDBY")

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xAAAAAA, 0x000000)
        Lcd.setCursor(10, 75)
        Lcd.print("1. Place on phone")
        Lcd.setCursor(10, 95)
        Lcd.print("2. Press [BTN A]")

        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(10, 145)
        Lcd.print(f"Last: {focus_seconds}s")
        Lcd.setCursor(10, 168)
        Lcd.print(f"Score: {score}")

    elif current_state == STATE_FOCUS:
        mins = focus_seconds // 60
        secs = focus_seconds % 60

        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0x00FF00, 0x000000)
        Lcd.setCursor(10, 32)
        Lcd.print("FOCUS")

        Lcd.setFont(M5.Lcd.FONTS.DejaVu24)
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(10, 80)
        Lcd.print(f"{mins:02d}:{secs:02d}")

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0x00FF88, 0x000000)
        Lcd.setCursor(10, 125)
        Lcd.print(f"Score: {score}")

        Lcd.setTextColor(0x777777, 0x000000)
        Lcd.setCursor(10, 180)
        Lcd.print("LEAVE PHONE")

# ==============================================================================
# 5. AZIONI SESSIONE
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
    last_activity_ms = now  # Reset del timeout di spegnimento display
    current_state = STATE_FOCUS
    render_ui()

def interrupt_session():
    global current_state, last_activity_ms
    current_state = STATE_INTERRUPTED
    trigger_pingu_alert()
    
    try:
        sync_session(
            score=score,
            focus_seconds=focus_seconds,
            danger_count=1,
            last_rssi=0,
            battery=get_battery_percentage(),
            log_cb=render_sync_console
        )
    except Exception as e:
        print("[Sync] Errore:", e)

    current_state = STATE_IDLE
    last_activity_ms = time.ticks_ms()
    display_on()
    render_ui()

# ==============================================================================
# 6. CICLO PRINCIPALE
# ==============================================================================
render_ui()

while True:
    M5.update()
    now = time.ticks_ms()
    acc_sample = read_accel()

    # --- TASTO A (Start / Stop Manuale) ---
    if BtnA.wasPressed():
        last_activity_ms = now
        if current_state in (STATE_IDLE, STATE_INTERRUPTED):
            start_session()
        elif current_state == STATE_FOCUS:
            current_state = STATE_IDLE
            display_on()
            try:
                sync_session(
                    score=score,
                    focus_seconds=focus_seconds,
                    danger_count=0,
                    last_rssi=0,
                    battery=get_battery_percentage(),
                    log_cb=render_sync_console
                )
            except Exception as e:
                print("[Sync] Errore:", e)
            render_ui()

    # --- TASTO B (Peek: riaccende lo schermo) ---
    if BtnB.wasPressed():
        last_activity_ms = now
        peek_until_ms = time.ticks_add(now, PEEK_DURATION_MS)
        if not is_display_on:
            display_on()
            render_ui()

    # --- STATO FOCUS ---
    if current_state == STATE_FOCUS:
        if detector.update(acc_sample):
            interrupt_session()
            continue

        # Lampeggio discreto ogni 4s
        if time.ticks_diff(now, last_heartbeat_ms) >= 4000:
            last_heartbeat_ms = now
            led_blink(15)

        # Aggiornamento UI ogni 1 secondo
        if time.ticks_diff(now, last_ui_tick) >= 1000:
            last_ui_tick = now
            focus_seconds += 1
            score += 2
            if focus_seconds % 60 == 0:
                score += 50
            if is_display_on:
                render_ui()

        # Spegnimento se inattivo e non in sbirciata
        if is_display_on:
            is_peeking = time.ticks_diff(peek_until_ms, now) > 0
            if not is_peeking and time.ticks_diff(now, last_activity_ms) > SCREEN_TIMEOUT_MS:
                display_off()

    # --- STATO IDLE ---
    elif current_state == STATE_IDLE:
        # Controllo movimento per risveglio dallo standby
        dx = acc_sample[0] - detector.gravity[0]
        dy = acc_sample[1] - detector.gravity[1]
        dz = acc_sample[2] - detector.gravity[2]
        
        # Se si muove in IDLE: aggiorna solo il timer di attività per non farlo spegnere
        if math.sqrt(dx**2 + dy**2 + dz**2) > 0.35:
            last_activity_ms = now
            # Ridisegna SOLO se lo schermo era spento, evitando il flickering a 25Hz
            if not is_display_on:
                display_on()
                render_ui()

        # Spegnimento display in standby
        if is_display_on and time.ticks_diff(now, last_activity_ms) > SCREEN_TIMEOUT_MS:
            display_off()

    time.sleep_ms(40)