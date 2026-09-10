import math
import time
import machine
from machine import Pin
import M5
from M5 import BtnA, BtnB, Imu, Lcd, Power, Speaker
from libs.network_client import update_user_points, initial_sync
from libs.motion_detector import SmartMotionDetector
from libs.offline_storage import save_pending_sync, get_pending_syncs

# ==============================================================================
# 1. HARDWARE & SETUP
# ==============================================================================
M5.begin()
Lcd.setBrightness(80)
Lcd.clear(0x000000)

try:
    led = Pin(10, Pin.OUT)
    led.value(1)  # 1 = spento (active-low)
except Exception:
    led = None

def led_blink(duration_ms=15):
    if led:
        led.value(0)
        time.sleep_ms(duration_ms)
        led.value(1)

BRIGHT_ACTIVE = 80
BRIGHT_OFF = 0
SCREEN_TIMEOUT_MS = 10000
PEEK_DURATION_MS = 5000
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
# 2. AUDIO PLAYBACK HELPER
# ==============================================================================
def play_wav(path, volume=240):
    """Riproduce un file WAV assicurando lo spegnimento dell'amplificatore I2S a fine traccia."""
    try:
        Speaker.begin()
        Speaker.setVolume(volume)
        Speaker.playWavFile(path)
        while Speaker.isPlaying():
            time.sleep_ms(20)
        Speaker.stop()
        Speaker.end()
    except Exception as e:
        print(f"[Audio] Error playing {path}:", e)

# ==============================================================================
# 3. PIXEL ART SPRITES (Stardew Valley Style)
# ==============================================================================
# Palette base
C_SOIL_DARK    = 0x4A2500
C_SOIL_LIGHT   = 0x733804
C_STEM_GREEN   = 0x248810
C_LEAF_BRIGHT  = 0x5CD632

# Palette pianta morta / appassita (toni terra secca e fieno)
C_DEAD_STEM    = 0x5A5928  # Stelo ingiallito/secco
C_DEAD_LEAF    = 0x826C34  # Foglia marrone morta
C_DEAD_SHADOW  = 0x52441E  # Ombra foglia secca

def draw_tilled_soil(cx, cy):
    Lcd.fillRect(cx - 24, cy + 18, 48, 10, C_SOIL_DARK)
    Lcd.fillRect(cx - 20, cy + 16, 40, 3, C_SOIL_LIGHT)
    Lcd.fillRect(cx - 16, cy + 22, 10, 2, C_SOIL_LIGHT)
    Lcd.fillRect(cx + 8, cy + 20, 12, 2, C_SOIL_LIGHT)

def draw_sprout(cx, cy):
    draw_tilled_soil(cx, cy)
    Lcd.fillRect(cx - 1, cy + 8, 3, 10, C_STEM_GREEN)
    Lcd.fillRect(cx - 6, cy + 4, 5, 4, C_LEAF_BRIGHT)
    Lcd.fillRect(cx + 2, cy + 2, 6, 4, C_LEAF_BRIGHT)

def draw_growing_plant(cx, cy):
    draw_tilled_soil(cx, cy)
    Lcd.fillRect(cx - 2, cy - 2, 4, 20, C_STEM_GREEN)
    Lcd.fillRect(cx - 10, cy + 6, 8, 4, C_LEAF_BRIGHT)
    Lcd.fillRect(cx + 2, cy + 4, 9, 4, C_LEAF_BRIGHT)
    Lcd.fillRect(cx - 8, cy - 2, 6, 4, C_LEAF_BRIGHT)
    Lcd.fillRect(cx + 2, cy - 4, 7, 4, C_LEAF_BRIGHT)

def draw_parsnip_mature(cx, cy):
    draw_tilled_soil(cx, cy)
    Lcd.fillRect(cx - 1, cy + 4, 3, 14, C_STEM_GREEN)
    Lcd.fillRect(cx - 7, cy + 2, 6, 3, C_LEAF_BRIGHT)
    Lcd.fillRect(cx + 2, cy + 1, 6, 3, C_LEAF_BRIGHT)
    Lcd.fillRect(cx - 6, cy - 12, 12, 14, 0xFFE082)
    Lcd.fillRect(cx - 4, cy + 2, 8, 4, 0xFFCA28)
    Lcd.fillRect(cx - 2, cy + 6, 4, 3, 0xD4A017)

def draw_blueberry_mature(cx, cy):
    draw_tilled_soil(cx, cy)
    Lcd.fillRect(cx - 14, cy - 8, 28, 26, C_STEM_GREEN)
    Lcd.fillRect(cx - 12, cy - 10, 24, 4, C_LEAF_BRIGHT)
    Lcd.fillRect(cx - 9, cy - 4, 6, 6, 0x2266FF)
    Lcd.fillRect(cx + 3, cy - 6, 6, 6, 0x1144DD)
    Lcd.fillRect(cx - 4, cy + 4, 7, 7, 0x4488FF)
    Lcd.fillRect(cx + 4, cy + 6, 6, 6, 0x2266FF)

def draw_ancient_fruit_mature(cx, cy):
    draw_tilled_soil(cx, cy)
    Lcd.fillRect(cx - 2, cy - 4, 5, 22, 0x1A591E)
    Lcd.fillRect(cx - 10, cy + 8, 8, 3, 0xFFA000)
    Lcd.fillRect(cx + 3, cy + 5, 8, 3, 0xFFA000)
    Lcd.fillRect(cx - 8, cy - 16, 17, 18, 0x05E5D0)
    Lcd.fillRect(cx - 6, cy - 18, 13, 3, 0x76FFEA)
    Lcd.fillRect(cx - 3, cy - 10, 7, 8, 0xFFFFFF)

def draw_withered_crop(cx, cy):
    """
    Sprite pixel art stile Stardew Valley:
    stelo secco piegato a U verso il suolo, foglia accartocciata cadente
    e foglia marrone staccata a terra.
    """
    draw_tilled_soil(cx, cy)

    # Stelo verticale secco
    Lcd.fillRect(cx - 8, cy + 6, 4, 11, C_DEAD_STEM)
    
    # Curva ad arco dello stelo spezzato
    Lcd.fillRect(cx - 6, cy + 2, 4, 4, C_DEAD_STEM)
    Lcd.fillRect(cx - 2, cy - 4, 6, 4, C_DEAD_STEM)
    Lcd.fillRect(cx + 4, cy - 1, 4, 4, C_DEAD_STEM)
    
    # Apice cadente con foglia appassita
    Lcd.fillRect(cx + 6, cy + 2, 6, 5, C_DEAD_LEAF)
    Lcd.fillRect(cx + 9, cy + 6, 4, 3, C_DEAD_SHADOW)

    # Foglia morta staccata e caduta a terra sulla destra
    Lcd.fillRect(cx + 12, cy + 14, 5, 3, C_DEAD_LEAF)
    Lcd.fillRect(cx + 16, cy + 15, 3, 2, C_DEAD_SHADOW)

def draw_crop_stage(crop_key, progress_ratio, cx=67, cy=72):
    if progress_ratio < 0.25:
        draw_sprout(cx, cy)
    elif progress_ratio < 0.80:
        draw_growing_plant(cx, cy)
    else:
        if crop_key == "PARSNIP":
            draw_parsnip_mature(cx, cy)
        elif crop_key == "BLUEBERRY":
            draw_blueberry_mature(cx, cy)
        elif crop_key == "ANCIENT_FRUIT":
            draw_ancient_fruit_mature(cx, cy)
        else:
            draw_growing_plant(cx, cy)

# ==============================================================================
# 4. MODELLO DATI CONTRATTI & STATO
# ==============================================================================
USER_ID = "1d27f428-ac94-4f9e-82d0-f2a62e6c2bea"
user_name = "Connecting..."
total_points = 0

STATE_IDLE = "IDLE"
STATE_REVIEW = "REVIEW"
STATE_FOCUS = "FOCUS"
STATE_INTERRUPTED = "INTERRUPTED"

CROPS = [
    {
        "id": "PARSNIP",
        "name": "Parsnip",
        "target_sec": 60,
        "bonus": 50,
        "color": 0xFFE082
    },
    {
        "id": "BLUEBERRY",
        "name": "Blueberry",
        "target_sec": 30 * 60,
        "bonus": 500,
        "color": 0x4488FF
    },
    {
        "id": "ANCIENT_FRUIT",
        "name": "Ancient Fruit",
        "target_sec": 60 * 60,
        "bonus": 1500,
        "color": 0x05E5D0
    }
]
selected_crop_idx = 0

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
# 5. GRAFICA & UI
# ==============================================================================
def trigger_breach_alert():
    display_on()
    Lcd.clear(0x000000)
    
    # Sprite della pianta appassita
    draw_withered_crop(67, 75)
    
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0xFF2222, 0x000000)
    Lcd.setCursor(8, 138)
    Lcd.print("CROP WITHERED")

    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFF6666, 0x000000)
    Lcd.setCursor(20, 194)
    Lcd.print("Seed Lost: 0 XP")

    # Suono di fallimento
    play_wav("res/audio/whistle.wav")
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

def render_contract_review():
    Lcd.clear(0x000000)
    crop = CROPS[selected_crop_idx]

    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFA500, 0x000000)
    Lcd.setCursor(10, 12)
    Lcd.print("CROP CONTRACT")
    Lcd.drawLine(8, 28, 127, 28, 0x553311)

    Lcd.setTextColor(0x888888, 0x000000)
    Lcd.setCursor(8, 38)
    Lcd.print("Seed Type:")
    Lcd.setTextColor(crop["color"], 0x000000)
    Lcd.setCursor(8, 54)
    Lcd.print(crop["name"])

    Lcd.setTextColor(0x888888, 0x000000)
    Lcd.setCursor(8, 76)
    Lcd.print("Growth Time:")
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(8, 92)
    mins = crop["target_sec"] // 60
    Lcd.print(f"{mins} Minutes" if mins > 0 else f"{crop['target_sec']}s")

    Lcd.setTextColor(0x888888, 0x000000)
    Lcd.setCursor(8, 114)
    Lcd.print("Harvest Yield:")
    Lcd.setTextColor(0x00FF88, 0x000000)
    Lcd.setCursor(8, 130)
    Lcd.print(f"+{crop['bonus']} XP + Crop")

    Lcd.drawLine(8, 154, 127, 154, 0x444444)
    Lcd.setTextColor(0x00AAFF, 0x000000)
    Lcd.setCursor(6, 170)
    Lcd.print("[A] PLANT & LOCK")
    Lcd.setTextColor(0x777777, 0x000000)
    Lcd.setCursor(6, 198)
    Lcd.print("[B] NEXT SEED")

def render_ui():
    if not is_display_on:
        return

    if current_state == STATE_REVIEW:
        render_contract_review()
        return

    Lcd.clear(0x000000)
    bat = get_battery_percentage()
    bat_color = 0x00FF00 if bat > 30 else (0xFFFF00 if bat > 15 else 0xFF0000)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(bat_color, 0x000000)
    Lcd.setCursor(95, 8)
    Lcd.print(f"{bat}%")

    crop = CROPS[selected_crop_idx]

    if current_state == STATE_IDLE:
        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0x00FF88, 0x000000)
        Lcd.setCursor(8, 20)
        Lcd.print("GREENHOUSE")

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0x00AAFF, 0x000000)
        Lcd.setCursor(8, 48)
        Lcd.print(f"Farm: {user_name}")
        Lcd.setCursor(8, 66)
        Lcd.print(f"Total: {total_points} XP")

        Lcd.setTextColor(0x888888, 0x000000)
        Lcd.setCursor(8, 95)
        Lcd.print("Ready to plant:")
        Lcd.setTextColor(crop["color"], 0x000000)
        Lcd.setCursor(8, 112)
        Lcd.print(f"> {crop['name']} <")

        Lcd.setTextColor(0xAAAAAA, 0x000000)
        Lcd.setCursor(8, 142)
        Lcd.print("[BTN B] Change")
        Lcd.setCursor(8, 162)
        Lcd.print("[BTN A] Contract")

        Lcd.setTextColor(0x666666, 0x000000)
        Lcd.setCursor(8, 195)
        Lcd.print(f"Last Yield: +{score}")

    elif current_state == STATE_FOCUS:
        target_sec = crop["target_sec"]
        remaining = max(0, target_sec - focus_seconds)
        mins = remaining // 60
        secs = remaining % 60
        progress_ratio = min(1.0, focus_seconds / target_sec)

        draw_crop_stage(crop["id"], progress_ratio, cx=67, cy=55)

        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0xFFFFFF, 0x000000)
        Lcd.setCursor(42, 100)
        Lcd.print(f"{mins:02d}:{secs:02d}")

        bar_x, bar_y, bar_w, bar_h = 15, 130, 105, 10
        Lcd.drawRect(bar_x, bar_y, bar_w, bar_h, 0x444444)
        fill_w = int(bar_w * progress_ratio)
        if fill_w > 0:
            Lcd.fillRect(bar_x, bar_y, fill_w, bar_h, crop["color"])

        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0x00FF88, 0x000000)
        Lcd.setCursor(18, 155)
        Lcd.print(f"Growing {crop['name']}")

        Lcd.setTextColor(0x555555, 0x000000)
        Lcd.setCursor(18, 195)
        Lcd.print("PHONE LOCKED")

# ==============================================================================
# 6. TRANSIZIONI & GESTIONE SESSIONE
# ==============================================================================
def start_session():
    global current_state, session_start_ms, focus_seconds, score, last_ui_tick, last_activity_ms
    display_on()
    
    # 1. Suono di semina prima di armare l'IMU
    play_wav("res/audio/seeds.wav")
    
    # 2. Assestamento per evitare che vibrazioni audio/meccaniche creino falsi positivi
    time.sleep_ms(CALIBRATION_SETTLE_MS)
    
    # 3. Calibrazione di zero assoluto dell'accelerometro
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
    score = 0

    trigger_breach_alert()

    current_state = STATE_IDLE
    last_activity_ms = time.ticks_ms()
    display_on()
    render_ui()

def complete_session():
    global current_state, last_activity_ms, score, total_points
    current_state = STATE_IDLE
    display_on()

    crop = CROPS[selected_crop_idx]
    score = crop["bonus"]

    # --- RENDER UI VITTORIA + AUDIO ---
    Lcd.clear(0x000000)
    draw_crop_stage(crop["id"], 1.0, cx=67, cy=60)
    
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0x00FF88, 0x000000)
    Lcd.setCursor(12, 120)
    Lcd.print("HARVESTED!")

    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(12, 150)
    Lcd.print(f"{crop['name']} Added!")
    Lcd.setTextColor(0xFFFF00, 0x000000)
    Lcd.setCursor(12, 172)
    Lcd.print(f"+{score} XP")

    play_wav("res/audio/harvest.wav")
    time.sleep_ms(150)
    play_wav("res/audio/reward.wav")
    time.sleep_ms(800)

    # Accredito immediato a display in locale
    total_points += score

    # --- TENTATIVO DI SINCRONIZZAZIONE RETE ---
    synced = False
    try:
        synced = update_user_points(USER_ID, score, plant_type=crop["id"], log_cb=render_sync_console)
    except Exception as e:
        print("[Sync] Errore rete:", e)

    if not synced:
        save_pending_sync(score, crop["id"])
        if render_sync_console:
            render_sync_console("SAVED OFFLINE")
        time.sleep_ms(1000)

    last_activity_ms = time.ticks_ms()
    render_ui()

# ==============================================================================
# 7. BOOTSTRAP INIZIALE
# ==============================================================================
render_ui()

local_pending = get_pending_syncs()
offline_accumulated = sum(item.get("score", 0) for item in local_pending)

try:
    profile = initial_sync(USER_ID, log_cb=render_sync_console)
    print("[Boot] Risultato initial_sync:", profile)
    
    if profile and isinstance(profile, dict) and profile.get("username"):
        user_name = profile["username"]
        total_points = profile["totalPoints"]
    else:
        user_name = "Offline"
        total_points = offline_accumulated
except Exception as err:
    print("[Boot] Sync profilazione fallita:", err)
    user_name = "Offline"
    total_points = offline_accumulated

last_activity_ms = time.ticks_ms()
display_on()
render_ui()

# ==============================================================================
# 8. MAIN LOOP
# ==============================================================================
while True:
    M5.update()
    now = time.ticks_ms()
    acc_sample = read_accel()

    # --- TASTO A (Firma/Inizia o Peek) ---
    if BtnA.wasPressed():
        last_activity_ms = now
        if current_state in (STATE_IDLE, STATE_INTERRUPTED):
            current_state = STATE_REVIEW
            display_on()
            render_ui()
        elif current_state == STATE_REVIEW:
            start_session()
        elif current_state == STATE_FOCUS:
            peek_until_ms = time.ticks_add(now, PEEK_DURATION_MS)
            if not is_display_on:
                display_on()
                render_ui()

    # --- TASTO B (Scelta seme / Annulla contratto / Peek) ---
    if BtnB.wasPressed():
        last_activity_ms = now
        if current_state == STATE_IDLE:
            selected_crop_idx = (selected_crop_idx + 1) % len(CROPS)
            display_on()
            render_ui()
        elif current_state == STATE_REVIEW:
            current_state = STATE_IDLE
            display_on()
            render_ui()
        elif current_state == STATE_FOCUS:
            peek_until_ms = time.ticks_add(now, PEEK_DURATION_MS)
            if not is_display_on:
                display_on()
                render_ui()

    # --- STATO FOCUS (COLTIVAZIONE ATTIVA) ---
    if current_state == STATE_FOCUS:
        if detector.update(acc_sample):
            interrupt_session()
            continue

        target_sec = CROPS[selected_crop_idx]["target_sec"]

        # LED Heartbeat verde ogni 4s
        if time.ticks_diff(now, last_heartbeat_ms) >= 4000:
            last_heartbeat_ms = now
            led_blink(15)

        # Tick di avanzamento al secondo
        if time.ticks_diff(now, last_ui_tick) >= 1000:
            last_ui_tick = now
            focus_seconds += 1

            if focus_seconds >= target_sec:
                complete_session()
                continue

            if is_display_on:
                render_ui()

        # Timeout spegnimento display
        if is_display_on:
            is_peeking = time.ticks_diff(peek_until_ms, now) > 0
            if not is_peeking and time.ticks_diff(now, last_activity_ms) > SCREEN_TIMEOUT_MS:
                display_off()

    # --- STATO IDLE & REVIEW ---
    elif current_state in (STATE_IDLE, STATE_REVIEW):
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