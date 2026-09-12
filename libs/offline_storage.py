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

def save_pending_sync(score, plant_identifier, seed_identifier):
    """Queues a not synced harvest in the local file."""
    pending = get_pending_syncs()
    pending.append({
        "score": score,
        "plantIdentifier": plant_identifier,
        "seedIdentifier": seed_identifier
    })
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(pending, f)
        print(f"[Storage] Saved offline: +{score} XP, {plant_identifier} (In queue: {len(pending)})")
        return True
    except Exception as e:
        print("[Storage] Error trying to save offline:", e)
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