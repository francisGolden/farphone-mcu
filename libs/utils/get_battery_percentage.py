from M5 import Power

def get_battery_percentage():
    try:
        level = Power.getBatteryLevel()
        return level if isinstance(level, (int, float)) and 0 <= level <= 100 else None
    except Exception:
        return None