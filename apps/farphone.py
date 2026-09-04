import M5
from M5 import Lcd, Speaker, Power, Imu
import math
import bluetooth
import time
import config
from libs.network_client import sync_session

# --- Hardware Initialization ---
M5.begin()
Speaker.begin()
Speaker.setVolume(255)
Lcd.clear(0x000000)

# --- Display Brightness & Sleep Settings ---
BRIGHT_ACTIVE = 80       # Normal brightness (0-100 o 0-255 depending on the build)
BRIGHT_DIM = 10          # Reduced brightness in idle mode
INACTIVITY_TIMEOUT_MS = 10000  # 10 seconds before the brightness is lowered
MOTION_THRESHOLD = 0.25  # Soglia variazione accelerazione in G

last_activity_time = time.ticks_ms()
is_dimmed = False
prev_acc = (0.0, 0.0, 0.0)

# Configure initial brightness
Lcd.setBrightness(BRIGHT_ACTIVE)

# Target Feasycom FSC-BP108 MAC Address
TARGET_MAC = bytes([0xDC, 0x0D, 0x30, 0x17, 0x45, 0x7D])
_IRQ_SCAN_RESULT = 5

# Timing configurations
SCAN_INTERVAL_MS = 5000   # BLE scan evaluation cycle (5s)
SCAN_WINDOW_MS = 1200     # Active listening window (1.2s)

# Gamification and session state
score = 0
streak_cycles = 0
focus_seconds = 0
danger_count = 0
in_danger_zone = False

last_sync_time = time.ticks_ms()
samples = []

# --- Sync state ---
last_sync_time = time.ticks_ms()
last_successful_sync_ms = None  # None until the first successful sync

def bt_irq(event, data):
    global samples
    if event == _IRQ_SCAN_RESULT:
        addr_type, addr, adv_type, rssi, adv_data = data
        if addr == TARGET_MAC:
            samples.append(rssi)

# Initialize BLE stack in scanner mode
ble = bluetooth.BLE()
ble.active(True)
ble.irq(bt_irq)

def get_last_sync_label():
    """Formats the time elapsed since the last successful sync."""
    if last_successful_sync_ms is None:
        return "Sync: --"
    
    elapsed_sec = time.ticks_diff(time.ticks_ms(), last_successful_sync_ms) // 1000
    if elapsed_sec < 60:
        return f"Sync: {elapsed_sec}s ago"
    elif elapsed_sec < 3600:
        return f"Sync: {elapsed_sec // 60}m ago"
    else:
        return f"Sync: {elapsed_sec // 3600}h ago"

def get_battery_percentage():
    """
    Returns the remaining battery level (0-100%).
    Falls back to None if charging circuitry isn't responding.
    """
    try:
        # Power.getBatteryLevel() get whole battery percentage (0-100)
        level = Power.getBatteryLevel()
        return level if level is not None else 100
    except Exception:
        return 100
    
def check_motion_and_dimmer():
    """Checks the IMU for physical motion and adjusts screen brightness accordingly."""
    global last_activity_time, is_dimmed, prev_acc
    
    try:
        # Read the acceleration on axis x, y, z
        acc = Imu.getAccel()
        ax, ay, az = acc[0], acc[1], acc[2]
        
        # Calculate difference compared to previous reading
        dx = ax - prev_acc[0]
        dy = ay - prev_acc[1]
        dz = az - prev_acc[2]
        prev_acc = (ax, ay, az)
        
        delta = math.sqrt(dx * dx + dy * dy + dz * dz)
        
        # If there is a movement, restart the timer and wake up the screen
        if delta > MOTION_THRESHOLD:
            last_activity_time = time.ticks_ms()
            if is_dimmed:
                Lcd.setBrightness(BRIGHT_ACTIVE)
                is_dimmed = False
                
    except Exception:
        pass

    # If there is no movement for the INACTIVITY_TIMEOUT_MS, lower the brightness
    if not is_dimmed and time.ticks_diff(time.ticks_ms(), last_activity_time) > INACTIVITY_TIMEOUT_MS:
        Lcd.setBrightness(BRIGHT_DIM)
        is_dimmed = True

def draw_pingu_face():
    """Draws Pingu's alert face fitted perfectly for 135x240 portrait."""
    Lcd.clear(0x000000)
    
    # Head & beak (centered at X=67)
    Lcd.fillCircle(67, 80, 42, 0x111111)   # Head
    Lcd.fillCircle(54, 66, 10, 0xFFFFFF)   # Left eye
    Lcd.fillCircle(80, 66, 10, 0xFFFFFF)   # Right eye
    Lcd.fillCircle(56, 66, 4, 0x000000)    # Left pupil
    Lcd.fillCircle(78, 66, 4, 0x000000)    # Right pupil
    Lcd.fillCircle(67, 92, 14, 0xFFA500)   # Beak base
    Lcd.fillCircle(67, 92, 8, 0x880000)    # Open trumpet mouth
    
    # Alert Title
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0xFF0000, 0x000000)
    Lcd.setCursor(12, 145)
    Lcd.print("NOOT NOOT!")
    
    # Subtitle cleanly split onto two lines
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(24, 180)
    Lcd.print("PUT PHONE")
    Lcd.setCursor(44, 200)
    Lcd.print("DOWN!")

def trigger_pingu_alert():
    """Displays alert graphics and plays WAV with smooth fade-out to prevent pop noise."""
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
    time.sleep_ms(1200)

def update_game_logic(avg_rssi):
    """Calculates scores, streaks, penalties, and danger events based on RSSI."""
    global score, streak_cycles, focus_seconds, danger_count, in_danger_zone
    
    if avg_rssi is None or avg_rssi <= -80:
        # Safe / Detox Zone
        in_danger_zone = False
        score += 10
        streak_cycles += 1
        focus_seconds += 5
        delta_label = "+10"
        status = "DETOX"
        color = 0x00FF00
        
        # Streak Bonus: awarded every 60 consecutive seconds (12 cycles)
        if streak_cycles > 0 and streak_cycles % 12 == 0:
            score += 50
            delta_label = "+60 STREAK!"
            
    elif -80 < avg_rssi <= -65:
        # Warning Zone (Phone is nearby)
        in_danger_zone = False
        streak_cycles = 0
        delta_label = "+0"
        status = "WARNING"
        color = 0xFFFF00
        
    else:
        # Danger Zone (Phone in hand / too close)
        streak_cycles = 0
        score = max(0, score - 5)
        delta_label = "-5 PENALTY"
        status = "DANGER!"
        color = 0xFF0000
        
        # Trigger Pingu event only on entering the danger threshold
        if not in_danger_zone:
            in_danger_zone = True
            danger_count += 1
            trigger_pingu_alert()
            
    return status, delta_label, color

def render_dashboard(status, delta_label, color, avg_rssi, syncing=False):
    """Renders the balanced dashboard tailored for 135px width."""
    Lcd.clear(0x000000)
    
    if syncing:
        Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(0x00AAFF, 0x000000)
        Lcd.setCursor(14, 30)
        Lcd.print("SYNCING...")
        Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xAAAAAA, 0x000000)
        Lcd.setCursor(14, 65)
        Lcd.print("Uploading data")
        return
        
    # --- Top Bar ---
    # Score (left)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(8, 8)
    Lcd.print(f"{score}")

    # Battery (right side, max X=135 so 95 leaves 40px)
    bat = get_battery_percentage()
    bat_color = 0x00FF00 if bat > 30 else (0xFFFF00 if bat > 15 else 0xFF0000)
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(bat_color, 0x000000)
    Lcd.setCursor(95, 12)
    Lcd.print(f"{bat}%")
    
    # Delta indicator
    Lcd.setTextColor(color, 0x000000)
    Lcd.setCursor(8, 38)
    Lcd.print(delta_label)
    
    # Status Banner
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(color, 0x000000)
    Lcd.setCursor(8, 68)
    Lcd.print(status)
    
    # RSSI Signal
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xAAAAAA, 0x000000)
    Lcd.setCursor(8, 104)
    rssi_text = f"RSSI: {int(avg_rssi)}dBm" if avg_rssi is not None else "Away"
    Lcd.print(rssi_text)
    
    # Focus Timer
    mins = focus_seconds // 60
    secs = focus_seconds % 60
    Lcd.setCursor(8, 128)
    Lcd.print(f"Time: {mins:02d}:{secs:02d}")
    
    # Last Successful Sync
    Lcd.setTextColor(0x00AAFF, 0x000000)
    Lcd.setCursor(8, 152)
    Lcd.print(get_last_sync_label())
    
def render_sync_console(step_text):
    """Renders a simple log window on screen during sync."""
    Lcd.clear(0x000000)
    
    # Title
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0x00AAFF, 0x000000)
    Lcd.setCursor(10, 15)
    Lcd.print("CLOUD SYNC")
    
    # Action / Log Line
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(10, 55)
    Lcd.print(step_text)
    
    # Target endpoint preview
    Lcd.setTextColor(0x777777, 0x000000)
    Lcd.setCursor(10, 95)
    Lcd.print("Backend: Spring")

# --- Main Application Loop ---
while True:
    M5.update()
    check_motion_and_dimmer()
    samples = []
    
    # 1. BLE active scanning window
    ble.gap_scan(SCAN_WINDOW_MS, 30000, 30000)
    start_time = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start_time) < SCAN_WINDOW_MS:
        M5.update()
        check_motion_and_dimmer()
        time.sleep_ms(40)
        
    # 2. Compute average RSSI from gathered samples
    avg = sum(samples) / len(samples) if samples else None
    
    # 3. Process score rules & update display
    status, delta_label, color = update_game_logic(avg)
    
    # Wake up screen immediately on entering danger zone
    if in_danger_zone and is_dimmed:
        Lcd.setBrightness(BRIGHT_ACTIVE)
        is_dimmed = False
        last_activity_time = time.ticks_ms()
        
    render_dashboard(status, delta_label, color, avg)
    
    # 4. Check periodic sync interval
    if time.ticks_diff(time.ticks_ms(), last_sync_time) >= config.SYNC_INTERVAL_MS:
        sync_cb = render_sync_console if not is_dimmed else None
        
        # Stop BLE scan to release the shared radio for Wi-Fi
        try:
            ble.gap_scan(None)
        except Exception:
            pass
        time.sleep_ms(100)  # Brief grace period for RF PHY switch
        
        ok = sync_session(
            score=score,
            focus_seconds=focus_seconds,
            danger_count=danger_count,
            last_rssi=int(avg) if avg is not None else -999,
            battery=get_battery_percentage(),
            log_cb=sync_cb
        )
        last_sync_time = time.ticks_ms()
        
        if ok:
            last_successful_sync_ms = time.ticks_ms()
            
        render_dashboard(status, delta_label, color, avg)
        
    # 5. Low-power pause until next iteration
    pause = SCAN_INTERVAL_MS - SCAN_WINDOW_MS
    pause_start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), pause_start) < pause:
        M5.update()
        check_motion_and_dimmer()
        time.sleep_ms(100)