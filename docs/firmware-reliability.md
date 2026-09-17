# Firmware reliability — improvements branch

This change affects firmware only. The fixed test user ID, HTTP endpoints and request JSON fields remain unchanged. Local event IDs are never sent to Spring Boot; no new authentication or idempotency headers are added.

## Changes

- Completed/failed sessions are queued before animations, sounds and networking. A completed harvest is not presented as awarded when persistence fails.
- Queue updates write a temporary file and rename it after flushing and closing. A corrupt or invalid queue is reported rather than treated as empty and overwritten. Preserve the original file for recovery if `STORAGE ERROR` appears.
- Existing valid queue records remain readable. New records receive local IDs; startup retries migrate legacy IDs locally before transmission. Each successful offline submission is removed immediately rather than at the end of the entire batch.
- A successful harvest POST remains successful if the subsequent profile GET fails. Its acknowledged local record is removed before profile refresh.
- HTTP reads are bounded to 32 KiB (headers limited to 4 KiB) and use the remaining request budget for receive timeouts. Content-Length allows completion without waiting for connection closure; truncated responses fail. Synchronous DNS and connection setup still depend on the firmware's blocking APIs. Chunked transfer encoding is explicitly rejected; this client uses HTTP/1.0 requests.
- Invalid IMU calibration cannot start a session. Missing/non-finite reads are no longer replaced with a fictitious zero acceleration. A sustained read failure during focus returns to review with `IMU ERROR - RETRY`, without treating it as user movement or awarding a harvest.
- Unknown battery readings show `--%`, and B on the review screen is labelled `BACK`.
- Light sleep remains enabled, serial logs disabled, and the temporary harvest timing screen is disabled by default.

## Upload together with Thonny

Copy the following to the corresponding device paths, then restart the device:

- `apps/tamarix.py`
- `libs/session.py`
- `libs/offline_storage.py`
- `libs/network/network_client.py`
- `libs/motion_detector.py`
- `libs/frontend/ui_renderer.py`
- `libs/utils/get_battery_percentage.py`

Keep your device configuration; set `HARVEST_TIMING_SCREEN = False`. Keep `LIGHT_SLEEP_ENABLED = True` and `SERIAL_LOG_ENABLED = False`.

Do not erase `pending_sync.json` or `wifi_credentials.json`. Back up pending sessions from the device before deployment. A stale `pending_sync.json.tmp` is not considered a committed queue.

## Verification

Host regression command: `python3 -B -m unittest discover -s tests -q`.

On the device, check a normal harvest, an offline harvest followed by restart with Wi-Fi available, peek and motion interruption, and the display timeout. Verify the confirmed event is removed from the local queue. Compare battery use under the same conditions as previous tests.

Host tests simulate storage errors, invalid queues, profile failure after a successful POST, per-event acknowledgement, HTTP truncation/size/time limits, calibration failure, and persistence before animation. They do not establish power-loss guarantees for the particular on-device filesystem.

## Remaining limits

Delivery is not guaranteed to be exactly once: if the server accepts a POST but its response is lost, or the device loses power before persisting the acknowledgement, the record remains eligible for retry. No firmware-only change can determine the server's outcome in that case. This patch does not change the backend contract.

The queue is capped at 500 events; reaching capacity produces `STORAGE ERROR` rather than discarding old sessions. Offline profile caching, retrying older queued events without a restart, incremental rendering, and the broader hardware cleanup remain separate follow-up work. The fixed test user ID is deliberately retained.


## Quiet harvest completion and low battery

At the session deadline, the firmware saves the successful event in the existing
persistent offline queue, credits local XP once, and switches off the display.
No completion sound or Wi-Fi connection starts at this point. Pressing either
button or picking up the stick reveals the reward and attempts the usual sync.
This interaction does not count as a peek or a breach and does not start a new
session. Movement uses the session's calibrated detector, so slow tilting also
reveals the reward while brief vibrations are filtered.

A restart before reveal preserves the queued event for boot synchronization;
the deferred reward animation itself is kept in RAM and is not replayed after a
restart. A storage error remains visible instead of claiming that the reward was
saved.

Battery level is checked once per minute. At or below `LOW_BATTERY_PERCENT`
(default 15), a short, quiet tone and a four-second `LOW BATTERY` banner warn the
user, including during focus. This is the only intentional automatic alert added
by this feature. The warning rearms after a reading at least five percentage
points above the threshold (20% by default), or after restarting the app. Unknown
battery readings do not trigger it. Tone playback does not block motion sampling.

For this feature, upload `apps/tamarix.py`, `libs/session.py`,
`libs/constants.py`, and the new `libs/battery_monitor.py`, alongside the earlier
reliability changes listed above. `config.py` can optionally define
`LOW_BATTERY_PERCENT = 15`; preserve your existing device configuration.

Device checks: let a session expire without touching the stick (silent, dark),
then press either button or pick it up (one reward, one queued event). Repeat
without Wi-Fi and restart to verify offline recovery. To test the battery alert,
temporarily set the threshold above the current reading, restart, and verify a
single brief tone/banner without stopping the focus timer; restore 15 afterward.
