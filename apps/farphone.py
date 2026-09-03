import M5
from M5 import Lcd, Speaker
import bluetooth
import time

# 1. Initialize hardware
M5.begin()
Speaker.begin()
Speaker.setVolume(255)  # Maximum volume for the I2S/DAC speaker
Lcd.clear(0x000000)

# MAC address of the Feasycom FSC-BP108 beacon
TARGET_MAC = bytes([0xDC, 0x0D, 0x30, 0x17, 0x45, 0x7D])
_IRQ_SCAN_RESULT = 5

# Scan timing
SCAN_INTERVAL_MS = 5000   # Evaluation every 5 seconds
SCAN_WINDOW_MS = 1200     # 1.2-second radio sampling window

# Gamification & state parameters
score = 0
streak_cycles = 0
focus_seconds = 0
in_danger_zone = False

samples = []

def bt_irq(event, data):
    global samples
    if event == _IRQ_SCAN_RESULT:
        addr_type, addr, adv_type, rssi, adv_data = data
        if addr == TARGET_MAC:
            samples.append(rssi)

# Start BLE stack
ble = bluetooth.BLE()
ble.active(True)
ble.irq(bt_irq)

def draw_pingu_face():
    """Draw Pingu's face with geometric primitives full screen"""
    Lcd.clear(0x000000)
    
    # Black head
    Lcd.fillCircle(67, 95, 46, 0x111111)
    
    # White eyes with black pupils
    Lcd.fillCircle(52, 75, 11, 0xFFFFFF)
    Lcd.fillCircle(82, 75, 11, 0xFFFFFF)
    Lcd.fillCircle(55, 75, 4, 0x000000)
    Lcd.fillCircle(79, 75, 4, 0x000000)
    
    # Wide-open trumpet beak (orange with dark interior)
    Lcd.fillCircle(67, 108, 16, 0xFFA500)
    Lcd.fillCircle(67, 108, 9, 0x880000)
    
    # Warning text
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setTextColor(0xFF0000, 0x000000)
    Lcd.setCursor(18, 165)
    Lcd.print("NOOT NOOT!")
    
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(12, 195)
    Lcd.print("VIA QUEL TELEFONO!")

def trigger_pingu_alert():
    """Show Pingu, play the WAV, and gently close the audio channel to avoid a bump"""
    draw_pingu_face()
    try:
        # 1. Set the playback volume
        Speaker.setVolume(240)
        Speaker.playWavFile("res/audio/pingu.wav")
        
        # 2. Wait until the file is actively playing
        while Speaker.isPlaying():
            time.sleep_ms(20)
            
        # 3. Short software fade-out to remove DC offset on the speaker membrane
        Speaker.setVolume(0)
        time.sleep_ms(30)
        
        # 4. Explicitly stop the driver at zero volume
        Speaker.stop()
        
    except Exception as e:
        print("WAV playback error:", e)
        
    time.sleep_ms(1200)

def update_game_logic(avg_rssi):
    global score, streak_cycles, focus_seconds, in_danger_zone
    
    if avg_rssi is None or avg_rssi <= -80:
        # Detox zone (phone absent or beyond safety threshold)
        in_danger_zone = False
        score += 10
        streak_cycles += 1
        focus_seconds += 5
        delta_label = "+10"
        status = "DETOX"
        color = 0x00FF00
        
        # Streak bonus: every continuous minute (12 cycles of 5s)
        if streak_cycles > 0 and streak_cycles % 12 == 0:
            score += 50
            delta_label = "+60 STREAK!"
            
    elif -80 < avg_rssi <= -65:
        # Attention zone (phone nearby)
        in_danger_zone = False
        streak_cycles = 0
        delta_label = "+0"
        status = "ATTENZIONE"
        color = 0xFFFF00
        
    else:
        # Danger zone (phone in hand or too close)
        streak_cycles = 0
        score = max(0, score - 5)
        delta_label = "-5 PENALITA"
        status = "PERICOLO!"
        color = 0xFF0000
        
        # Trigger only on the first detection of entering the danger zone
        if not in_danger_zone:
            in_danger_zone = True
            trigger_pingu_alert()
            
    return status, delta_label, color

def render_dashboard(status, delta_label, color, avg_rssi):
    """Render the standard dashboard"""
    Lcd.clear(0x000000)
    
    # 1. Total score
    Lcd.setFont(M5.Lcd.FONTS.DejaVu24)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    Lcd.setCursor(10, 8)
    Lcd.print(f"{score} PTS")
    
    # 2. Point change
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(color, 0x000000)
    Lcd.setCursor(115, 16)
    Lcd.print(delta_label)
    
    # 3. Current status
    Lcd.setFont(M5.Lcd.FONTS.DejaVu18)
    Lcd.setCursor(10, 48)
    Lcd.print(status)
    
    # 4. Measured RSSI
    Lcd.setFont(M5.Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xAAAAAA, 0x000000)
    Lcd.setCursor(10, 75)
    rssi_text = f"RSSI: {int(avg_rssi)} dBm" if avg_rssi is not None else "Beacon: Assente"
    Lcd.print(rssi_text)
    
    # 5. Focus time timer
    mins = focus_seconds // 60
    secs = focus_seconds % 60
    Lcd.setCursor(10, 100)
    Lcd.print(f"Tempo: {mins:02d}:{secs:02d}")

# Main loop
while True:
    M5.update()
    samples = []
    
    # 1. Active BLE scan window
    ble.gap_scan(SCAN_WINDOW_MS, 30000, 30000)
    start_time = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start_time) < SCAN_WINDOW_MS:
        M5.update()
        time.sleep_ms(40)
        
    # 2. Moving average calculation
    avg = sum(samples) / len(samples) if samples else None
    
    # 3. Score calculation (and optional Pingu animation/audio)
    status, delta_label, color = update_game_logic(avg)
    
    # 4. Interface update
    render_dashboard(status, delta_label, color, avg)
    
    # 5. Low-power radio pause
    pause = SCAN_INTERVAL_MS - SCAN_WINDOW_MS
    pause_start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), pause_start) < pause:
        M5.update()
        time.sleep_ms(100)