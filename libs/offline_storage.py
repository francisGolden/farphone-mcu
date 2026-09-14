import json
import os

STORAGE_FILE = "pending_sync.json"

def get_pending_syncs():
    """Retrievs the list of saved sessions waiting for sync."""
    try:
        with open(STORAGE_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []
    
def save_pending_sync(score, seed_id, plant_id=None, harvestOutcome="SUCCESSFUL", duration_sec=0):
    items = get_pending_syncs()
    items.append({
        "xpEarned": score,
        "seedIdentifier": seed_id,
        "plantIdentifier": plant_id,
        "harvestOutcome": harvestOutcome,
        "durationSeconds": duration_sec
    })
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(items, f)
        print(f"[Storage] Saved offline: {harvestOutcome} ({score} XP, {duration_sec}s)")
        return True
    except Exception as e:
        print("[Storage] Error saving offline record:", e)
        return False

def clear_pending_syncs():
    """Removes or empties the queue after complete sync."""
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump([], f)
    except Exception:
        try:
            os.remove(STORAGE_FILE)
        except Exception:
            pass