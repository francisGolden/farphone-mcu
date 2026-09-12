import json
import os

STORAGE_FILE = "pending_sync.json"

def get_pending_syncs():
    """Restituisce la lista di sessioni salvate in attesa di sync."""
    try:
        with open(STORAGE_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def save_pending_sync(score, plant_identifier, seed_identifier):
    """Accoda un raccolto non inviato nel file locale."""
    pending = get_pending_syncs()
    pending.append({
        "score": score,
        "plantIdentifier": plant_identifier,
        "seedIdentifier": seed_identifier
    })
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(pending, f)
        print(f"[Storage] Salvato offline: +{score} XP, {plant_identifier} (Totali in coda: {len(pending)})")
        return True
    except Exception as e:
        print("[Storage] Errore salvataggio offline:", e)
        return False

def clear_pending_syncs():
    """Rimuove o svuota la coda dopo il sync completato."""
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump([], f)
    except Exception:
        try:
            os.remove(STORAGE_FILE)
        except Exception:
            pass