from M5 import Power

def get_battery_percentage():
    try:
        level = Power.getBatteryLevel()
        return level if level is not None else 100
    except Exception:
        return 100