"""Durable session outbox. Corrupt data is preserved and reported, never erased."""
from libs.diagnostic_log import log as print
import json
import os
import binascii

STORAGE_FILE = 'pending_sync.json'
MAX_EVENTS = 500


def _validate(items):
    if not isinstance(items, list):
        raise ValueError('Invalid offline queue')
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('seedIdentifier'), str):
            raise ValueError('Invalid offline event')
        for key in ('xpEarned', 'durationSeconds', 'peekCount'):
            value = item.get(key, 0)
            if not isinstance(value, int) or value < 0:
                raise ValueError('Invalid offline event field: ' + key)
        if item.get('harvestOutcome', 'SUCCESSFUL') not in ('SUCCESSFUL', 'FAILED'):
            raise ValueError('Invalid harvest outcome')
    return items


def get_pending_syncs():
    try:
        with open(STORAGE_FILE, 'r') as source:
            items = _validate(json.load(source))
    except OSError as exc:
        if exc.args and exc.args[0] == 2:  # Missing file is the only empty-queue case.
            return []
        raise
    if any('timestamp' in item for item in items):
        # Migrate legacy events atomically, even when the device is offline.
        items = [{key: value for key, value in item.items() if key != 'timestamp'}
                 for item in items]
        replace_pending_syncs(items)
    return items


def replace_pending_syncs(items):
    _validate(items)
    items = [{key: value for key, value in item.items() if key != 'timestamp'}
             for item in items]
    with open(STORAGE_FILE + '.tmp', 'w') as target:
        json.dump(items, target)
        target.flush()
    os.rename(STORAGE_FILE + '.tmp', STORAGE_FILE)


def queue_session(score, seed_id, plant_id=None, harvestOutcome='SUCCESSFUL',
                  duration_sec=0, peek_count=0, first_peek_sec=None):
    items = get_pending_syncs()
    if len(items) >= MAX_EVENTS:
        raise OSError('Offline queue full')
    event_id = binascii.hexlify(os.urandom(16)).decode()
    items.append(dict(eventId=event_id, xpEarned=score, seedIdentifier=seed_id,
        plantIdentifier=plant_id, harvestOutcome=harvestOutcome,
        durationSeconds=duration_sec, peekCount=peek_count, firstPeekSec=first_peek_sec))
    replace_pending_syncs(items)
    return event_id


def acknowledge_event(event_id):
    items = get_pending_syncs()
    replace_pending_syncs([item for item in items if item.get('eventId') != event_id])


def save_pending_sync(score, seed_id, plant_id=None, harvestOutcome='SUCCESSFUL',
                      duration_sec=0, peek_count=0, first_peek_sec=None):
    """Compatibility wrapper for callers that only need a success flag."""
    try:
        queue_session(score, seed_id, plant_id, harvestOutcome, duration_sec, peek_count, first_peek_sec)
        return True
    except (OSError, ValueError) as exc:
        print('[Storage] Unable to persist event:', exc)
        return False


def clear_pending_syncs():
    replace_pending_syncs([])
