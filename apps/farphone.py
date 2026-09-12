import math
import time
import random
import machine
from machine import Pin
import M5
from M5 import BtnA, BtnB, Imu, Lcd, Power, Speaker
from libs.network_client import update_user_points, initial_sync, fetch_user_raw, connect_wifi, disconnect_wifi
from libs.motion_detector import SmartMotionDetector
from libs.offline_storage import save_pending_sync, get_pending_syncs

# ==============================================================================
# 1. HARDWARE & POWER TUNING
# ==============================================================================
M5.begin()
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
# 2. AUDIO PLAYBACK (Anti-Pop Safe)
# ==============================================================================
def play_wav(path, volume=240):
    try:
        Speaker.begin()
        Speaker.setVolume(volume)
        Speaker.playWavFile(path)
        while Speaker.isPlaying():
            time.sleep_ms(20)
        # Discharge hardware bias gradually to eliminate popping
        Speaker.setVolume(0)
        time.sleep_ms(40)
        Speaker.stop()
        time.sleep_ms(20)
        Speaker.end()
    except Exception as e:
        print(f"[Audio] Playback error {path}:", e)

# ==============================================================================
# 3. INTENT SEEDS CATALOG & CROP LOOT TABLE
# ==============================================================================
# Rarity tiers: COM (60%), RAR (30%), LEG (10%)
SEEDS_CATALOG = [
    {
        "id": "SEED_LEARNING",
        "name": "Learning",
        "target_sec": 45 * 60,
        "bonus_base": 600,
        "accent_color": 0x44AAFF,
        "pool": [
            {"id": "ROSEMARY", "name": "Rosemary",      "rarity": "COM", "xp_mul": 1.0},
            {"id": "MINT",     "name": "Peppermint",    "rarity": "COM", "xp_mul": 1.0},
            {"id": "SALVIA",   "name": "White Sage",    "rarity": "RAR", "xp_mul": 1.5},
            {"id": "GINKGO",   "name": "Ginkgo Biloba", "rarity": "LEG", "xp_mul": 2.5}
        ]
    },
    {
        "id": "SEED_LABOUR",
        "name": "Labour",
        "target_sec": 30 * 60,
        "bonus_base": 500,
        "accent_color": 0xFFA500,
        "pool": [
            {"id": "COFFEE",    "name": "Coffee Bean",  "rarity": "COM", "xp_mul": 1.0},
            {"id": "BLACK_TEA", "name": "Black Tea",    "rarity": "COM", "xp_mul": 1.0},
            {"id": "GUARANA",   "name": "Wild Guarana", "rarity": "RAR", "xp_mul": 1.5},
            {"id": "CACAO",     "name": "Sacred Cacao", "rarity": "LEG", "xp_mul": 2.5}
        ]
    },
    {
        "id": "SEED_REST",
        "name": "Rest",
        "target_sec": 60 * 60,
        "bonus_base": 1200,
        "accent_color": 0x9955FF,
        "pool": [
            {"id": "CHAMOMILE", "name": "Chamomile",    "rarity": "COM", "xp_mul": 1.0},
            {"id": "LAVENDER",  "name": "Blue Lavender","rarity": "COM", "xp_mul": 1.0},
            {"id": "VALERIAN",  "name": "Valerian",     "rarity": "RAR", "xp_mul": 1.5},
            {"id": "MOON_LILY", "name": "Moon Lily",    "rarity": "LEG", "xp_mul": 3.0}
        ]
    },
    {
        "id": "SEED_ATTUNEMENT",
        "name": "Attunement",
        "target_sec": 20 * 60,
        "bonus_base": 350,
        "accent_color": 0xFFDD44,
        "pool": [
            {"id": "MYRTLE", "name": "Myrtle",      "rarity": "COM", "xp_mul": 1.0},
            {"id": "OLIVE",  "name": "Olive Branch","rarity": "RAR", "xp_mul": 1.5},
            {"id": "BODHI",  "name": "Bodhi Leaf",  "rarity": "LEG", "xp_mul": 3.0}
        ]
    },
    {
        "id": "SEED_NOURISHMENT",
        "name": "Nourishment",
        "target_sec": 15 * 60,
        "bonus_base": 250,
        "accent_color": 0x5CD632,
        "pool": [
            {"id": "FENNEL",    "name": "Wild Fennel",  "rarity": "COM", "xp_mul": 1.0},
            {"id": "MELISSA",   "name": "Sweet Melissa","rarity": "COM", "xp_mul": 1.0},
            {"id": "GINGER",    "name": "Golden Ginger","rarity": "RAR", "xp_mul": 1.5},
            {"id": "GOLD_ROOT", "name": "Sun Root",     "rarity": "LEG", "xp_mul": 2.5}
        ]
    },
    {
        "id": "SEED_RECREATION",
        "name": "Recreation",
        "target_sec": 60,  # 1 min test sprint
        "bonus_base": 100,
        "accent_color": 0xFF44AA,
        "pool": [
            {"id": "CLOVER",     "name": "Trifolium",    "rarity": "COM", "xp_mul": 1.0},
            {"id": "DANDELION",  "name": "Dandelion",    "rarity": "COM", "xp_mul": 1.0},
            {"id": "RED_SHROOM", "name": "Red Mushroom", "rarity": "RAR", "xp_mul": 1.5},
            {"id": "LUCKY_4",    "name": "Four-Leaf",    "rarity": "LEG", "xp_mul": 3.0}
        ]
    },
        {
        "id": "SEED_COVENANT",
        "name": "Covenant",
        "target_sec": 60 * 60,
        "bonus_base": 1500,
        "accent_color": 0xFF44AA,
        "pool": [
            {"id": "GRAPEVINE", "name": "Grapevine", "rarity": "COM", "xp_mul": 1.0},
            {"id": "ACACIA",  "name": "Acacia", "rarity": "COM", "xp_mul": 1.0},
            {"id": "MYRTLE", "name": "Myrtle", "rarity": "RAR", "xp_mul": 1.5},
            {"id": "IVY",    "name": "Ivy", "rarity": "LEG", "xp_mul": 3.0}
        ]
    }
]

def roll_random_crop(seed_data):
    roll = random.randint(1, 100)
    target_rarity = "COM"
    if roll > 90:
        target_rarity = "LEG"
    elif roll > 60:
        target_rarity = "RAR"

    candidates = [p for p in seed_data["pool"] if p["rarity"] == target_rarity]
    if not candidates:
        candidates = seed_data["pool"]
    return random.choice(candidates)

# ==============================================================================
# 4. PIXEL ART ENGINE
# ==============================================================================
C_SOIL_DARK   = 0x4A2500
C_SOIL_LIGHT  = 0x733804
C_STEM_GREEN  = 0x248810
C_LEAF_BRIGHT = 0x5CD632
C_DEAD_STEM   = 0x5A5928
C_DEAD_LEAF   = 0x826C34
C_DEAD_SHADOW = 0x52441E

def draw_tilled_soil(cx, cy):
    Lcd.fillRect(cx - 24, cy + 18, 48, 10, C_SOIL_DARK)
    Lcd.fillRect(cx - 20, cy + 16, 40, 3, C_SOIL_LIGHT)
    Lcd.fillRect(cx - 16, cy + 22, 10, 2, C_SOIL_LIGHT)
    Lcd.fillRect(cx + 8, cy + 20, 12, 2, C_SOIL_LIGHT)

def draw_mystery_sprout(cx, cy, progress_ratio):
    draw_tilled_soil(cx, cy)
    if progress_ratio < 0.35:
        Lcd.fillRect(cx - 1, cy + 8, 3, 10, C_STEM_GREEN)
        Lcd.fillRect(cx - 6, cy + 4, 5, 4, C_LEAF_BRIGHT)
        Lcd.fillRect(cx + 2, cy + 2, 6, 4, C_LEAF_BRIGHT)
    else:
        Lcd.fillRect(cx - 2, cy - 2, 4, 20, C_STEM_GREEN)
        Lcd.fillRect(cx - 10, cy + 6, 8, 4, C_LEAF_BRIGHT)
        Lcd.fillRect(cx + 2, cy + 4, 9, 4, C_LEAF_BRIGHT)
        # Mystery bud container
        Lcd.fillRect(cx - 6, cy - 14, 12, 12, 0x8833AA)
        Lcd.fillRect(cx - 4, cy - 16, 8, 3, 0xBA68C8)
        Lcd.setTextColor(0xFFFFFF, 0x8833AA)
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setCursor(cx - 3, cy - 14)
        Lcd.print("?")

def draw_withered_crop(cx, cy):
    draw_tilled_soil(cx, cy)
    Lcd.fillRect(cx - 8, cy + 6, 4, 11, C_DEAD_STEM)
    Lcd.fillRect(cx - 6, cy + 2, 4, 4, C_DEAD_STEM)
    Lcd.fillRect(cx - 2, cy - 4, 6, 4, C_DEAD_STEM)
    Lcd.fillRect(cx + 4, cy - 1, 4, 4, C_DEAD_STEM)
    Lcd.fillRect(cx + 6, cy + 2, 6, 5, C_DEAD_LEAF)
    Lcd.fillRect(cx + 12, cy + 14, 5, 3, C_DEAD_LEAF)
    Lcd.fillRect(cx + 16, cy + 15, 3, 2, C_DEAD_SHADOW)

def draw_revealed_plant(cx, cy, rarity_color):
    draw_tilled_soil(cx, cy)
    Lcd.drawCircle(cx, cy - 4, 18, rarity_color)
    Lcd.fillRect(cx - 2, cy - 6, 4, 24, C_STEM_GREEN)
    Lcd.fillRect(cx - 12, cy + 4, 10, 4, C_LEAF_BRIGHT)
    Lcd.fillRect(cx + 2, cy + 2, 11, 4, C_LEAF_BRIGHT)
    Lcd.fillCircle(cx, cy - 8, 9, rarity_color)
    Lcd.fillCircle(cx, cy - 8, 5, 0xFFFFFF)

# ==============================================================================
# 5. STATE & RUNTIME CONFIG
# ==============================================================================
USER_ID = "1d27f428-ac94-4f9e-82d0-f2a62e6c2bea"
user_name = "Connecting..."
total_points = 0

STATE_IDLE = "IDLE"
STATE_REVIEW = "REVIEW"
STATE_FOCUS = "FOCUS"
STATE_INTERRUPTED = "INTERRUPTED"

selected_seed_idx = 0
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
# 6. UI RENDERER
# ==============================================================================
def trigger_breach_alert():
    display_on()
    Lcd.clear(0x000000)
    draw_withered_crop(67, 75)

    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0xFF2222, 0x000000)
    Lcd.setCursor(8, 138)
    Lcd.print("CROP WITHERED")

    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xAAAAAA, 0x000000)
    Lcd.setCursor(10, 168)
    Lcd.print("Contract Breached!")
    Lcd.setTextColor(0xFF6666, 0x000000)
    Lcd.setCursor(18, 194)
    Lcd.print("Seed Lost: 0 XP")

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
    Lcd.setCursor(95, 6)
    Lcd.print(f"{bat}%")

    seed = SEEDS_CATALOG[selected_seed_idx]

    if current_state == STATE_IDLE:
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

    elif current_state == STATE_FOCUS:
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

# ==============================================================================
# 7. SESSION TRANSITIONS & REVEAL
# ==============================================================================
def start_session():
    global current_state, session_start_ms, focus_seconds, score, last_ui_tick, last_activity_ms
    display_on()

    play_wav("res/audio/seeds.wav")
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
    score = 0

    trigger_breach_alert()

    current_state = STATE_IDLE
    last_activity_ms = time.ticks_ms()
    display_on()
    render_ui()

def complete_session():
    global current_state, last_activity_ms, score, total_points, user_name
    current_state = STATE_IDLE
    display_on()

    seed = SEEDS_CATALOG[selected_seed_idx]

    # 1. Loot Table extraction
    picked_crop = roll_random_crop(seed)
    score = int(seed["bonus_base"] * picked_crop["xp_mul"])

    rarity_badge = {
        "COM": ("COMMON",    0x00FF88),
        "RAR": ("RARE",      0x00AAFF),
        "LEG": ("LEGENDARY", 0xFFA500)
    }[picked_crop["rarity"]]

    # 2. Suspense & Harvest Sound
    Lcd.clear(0x000000)
    draw_mystery_sprout(67, 60, 1.0)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(14, 120)
    Lcd.print("BLOOMING...")
    play_wav("res/audio/harvest.wav")
    time.sleep_ms(600)

    # 3. Reveal Step & Reward Sound
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
    Lcd.print(f"+{score} XP")

    play_wav("res/audio/reward.wav")
    time.sleep_ms(1500)

    # Optimistic local UI credit
    total_points += score

    # 4. HTTP Synchronisation with Single-Flight Profile Refresh
    synced = False
    try:
        # update_user_points sends the harvest and recovers the user profile in the same Wi-Fi session
        fresh_profile = update_user_points(
            USER_ID, 
            score, 
            seed_identifier=seed["id"], 
            plant_identifier=picked_crop["id"], 
            log_cb=render_sync_console
        )
        if fresh_profile and isinstance(fresh_profile, dict):
            synced = True
            user_name = fresh_profile.get("username", user_name)
            total_points = fresh_profile.get("totalPoints", total_points)
            print(f"[Sync] Profile refreshed: {user_name}, Total: {total_points} XP")
        elif fresh_profile is True:
            synced = True
    except Exception as e:
        print("[Sync] Network error:", e)

    if not synced:
        save_pending_sync(score, seed["id"], picked_crop["id"])
        if render_sync_console:
            render_sync_console("SAVED OFFLINE")
        time.sleep_ms(1000)

    last_activity_ms = time.ticks_ms()
    render_ui()

# ==============================================================================
# 8. BOOTSTRAP INITIALIZATION
# ==============================================================================
render_ui()

local_pending = get_pending_syncs()
offline_accumulated = sum(item.get("score", 0) for item in local_pending)

try:
    profile = initial_sync(USER_ID, log_cb=render_sync_console)
    print("[Boot] initial_sync result:", profile)
    if profile and isinstance(profile, dict) and profile.get("username"):
        user_name = profile["username"]
        total_points = profile["totalPoints"]
    else:
        user_name = "Offline"
        total_points = offline_accumulated
except Exception as err:
    print("[Boot] Sync failed:", err)
    user_name = "Offline"
    total_points = offline_accumulated

last_activity_ms = time.ticks_ms()
display_on()
render_ui()

# ==============================================================================
# 9. MAIN LOOP
# ==============================================================================
while True:
    M5.update()
    now = time.ticks_ms()
    acc_sample = read_accel()

    # --- BTN A (Confirm / Start / Peek) ---
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

    # --- BTN B (Cycle Intent / Cancel / Peek) ---
    if BtnB.wasPressed():
        last_activity_ms = now
        if current_state == STATE_IDLE:
            selected_seed_idx = (selected_seed_idx + 1) % len(SEEDS_CATALOG)
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

    # --- FOCUS ACTIVE STATE ---
    if current_state == STATE_FOCUS:
        if detector.update(acc_sample):
            interrupt_session()
            continue

        target_sec = SEEDS_CATALOG[selected_seed_idx]["target_sec"]

        if time.ticks_diff(now, last_heartbeat_ms) >= 4000:
            last_heartbeat_ms = now
            led_blink(15)

        if time.ticks_diff(now, last_ui_tick) >= 1000:
            last_ui_tick = now
            focus_seconds += 1

            if focus_seconds >= target_sec:
                complete_session()
                continue

            if is_display_on:
                render_ui()

        if is_display_on:
            is_peeking = time.ticks_diff(peek_until_ms, now) > 0
            if not is_peeking and time.ticks_diff(now, last_activity_ms) > SCREEN_TIMEOUT_MS:
                display_off()

    # --- IDLE & REVIEW STATE ---
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