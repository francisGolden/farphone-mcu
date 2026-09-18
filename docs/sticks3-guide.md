# StickS3 setup and technical guide

[Back to Tamarix](../README.md)

Installation, controls, configuration, prototype limitations, and troubleshooting.
Paths below are relative to the repository root unless stated otherwise.

## Install on a StickS3

### 1. Prepare the device

You will need a StickS3, a USB data cable, a computer with [Thonny](https://thonny.org/), and a phone for Wi-Fi setup. Backend synchronization also needs a reachable server and a 2.4 GHz Wi-Fi network.

Install the **StickS3 version of UIFlow2** using M5Burner, following the [official StickS3 flashing guide](https://docs.m5stack.com/en/uiflow2/sticks3/program). The project's device testing has used **UIFlow2 2.4.5**. Generic ESP32 MicroPython does not provide the required `M5` hardware APIs.

If the stick already runs a compatible UIFlow2 installation, you can upload the application without reflashing. Back up existing device files before flashing or replacing them.

### 2. Upload the complete application

Download or clone this repository. Connect the stick by USB, open Thonny, and select **MicroPython (ESP32)** and the device's serial port in the interpreter settings. Use **Stop/Restart** to stop a running application, then open **View → Files**. Thonny's file browser supports uploading files and directories through their context menus; see its [MicroPython guide](https://github.com/thonny/thonny/wiki/MicroPython).

Upload these items to the **device filesystem root**, preserving their directory structure:

| Repository item | Device location | Contents |
| --- | --- | --- |
| `apps/` | `apps/` | Application entry point |
| `libs/` | `libs/` | All application modules and subdirectories |
| `res/` | `res/` | Plant catalogue, Chronicles, character sprite, and audio files |
| `config.py` | `config.py` | Power, diagnostics, and configuration defaults |

The result should include:

```text
apps/
  tamarix.py
libs/
  battery_monitor.py
  constants.py
  diagnostic_log.py
  harvest_led.py
  motion_detector.py
  offline_storage.py
  power_manager.py
  session.py
  frontend/
    pixel_art_engine.py
    ui_renderer.py
  network/
    network_client.py
    wifi_credentials.py
    wifi_setup.py
  utils/
    get_battery_percentage.py
res/
  audio/
    harvest.wav
    reward.wav
    seeds.wav
    whistle.wav
  data/
    seeds_catalog.py
    chronicles.py
    tamarix_sprite.py
config.py
```

**Upload the complete set from the same revision.** Updating only the entry point can leave incompatible modules on the device. The network client belongs at `libs/network/network_client.py`; an old `libs/network_client.py` is not part of this layout. Tests and documentation do not need to be uploaded.

### 3. Set the test identity and startup

The prototype currently uses a fixed `USER_ID` in `apps/tamarix.py`. For synchronization, that ID must identify a user in your backend. There is no account registration or sign-in flow on the stick yet.

To launch manually, run this in Thonny's device shell from the filesystem root:

```python
exec(open("apps/tamarix.py").read(), globals())
```

For automatic startup, back up any existing device `main.py`, then create a `main.py` at the device root containing that same line. This repository does not supply a `main.py` or replace UIFlow's `boot.py`.

Set UIFlow2's **Boot Option** to **Run main.py directly** using M5Burner's configuration interface, then restart. This startup mode is described in the [official device guide](https://docs.m5stack.com/en/uiflow2/sticks3/program). Tamarix handles its own Wi-Fi setup.

#### Return to the UIFlow2 menu

To restore the menu, connect the stick by USB, open **Configure** in M5Burner, and change **Boot Option** to **Show startup menu and network setup**. Restart afterward. To resume Tamarix autostart, select **Run main.py directly** again. Keep the original UIFlow `boot.py` intact.

The [current official UIFlow boot source](https://github.com/m5stack/uiflow-micropython/blob/master/m5stack/fs/user/boot.py) also documents a StickS3 shortcut: hold **A while powering on or resetting** to enter the startup menu. In that implementation, this saves the menu boot option, so restore the direct-run option afterward if you want automatic Tamarix startup again. This shortcut has not been verified on this project's UIFlow2 2.4.5 installation; use M5Burner's configuration route if it does not work. Back up `main.py` before trying recovery shortcuts on older firmware.

### 4. Configure Wi-Fi and the server

On first launch, the stick opens setup automatically if its network or server address is missing.

1. Scan the first QR code to join the temporary `Tamarix-xxxx` network. Accept staying connected even if your phone reports no Internet access.
2. Press **B** for the second QR code. Scan it to open the setup page at `http://192.168.4.1`.
3. Select your nearby **2.4 GHz** network and enter its password. Hidden networks can be entered manually.
4. Enter the backend's base address, such as `http://192.168.178.45:8080`. Use the server's reachable address, not `localhost`, and omit endpoint paths such as `/api/harvest`.
5. Submit with **Connect thy stick** and wait for **Wi-Fi saved!** on the device. Reconnect your phone to its usual network.

The current client supports **HTTP**, without HTTPS. A server running on your computer must accept connections from the stick's network. The setup form checks the address format; it does not verify that the server is online.

Press **B** during the two-second startup prompt to change the network or server later. In setup, B cycles the QR codes and manual instructions; A exits. See the [full Wi-Fi setup guide](wifi-setup.md) for supported networks and troubleshooting.

## Use Tamarix

### Choose what to nurture

From the **THY GARDEN** screen, press **B** to browse intentions and **A** to review one.

| Intention | Current duration | Make room for… |
| --- | --- | --- |
| Nourishment | 15 minutes | A meal prepared or enjoyed with attention |
| Learning | 45 minutes | Reading, studying, and curiosity |
| Rest | 60 minutes | Quiet and recovery |
| Labour | 30 minutes | Focused work or making something |
| Recreation | 1 minute | Play and enjoyment; currently a short test session |
| Attunement | 20 minutes | Reflection and awareness |
| Covenant | 60 minutes | Presence with other people |

These durations come from `res/data/seeds_catalog.py`. Recreation is useful for trying the complete experience before starting a longer session.

### Plant, leave it still, and return when ready

Before starting, take your phone and stick **as far from where you will spend the session as possible, ideally to another room**. Lay the phone **screen down on a stable surface** and rest the stick **on the back of the phone**, with its display facing up and its buttons accessible. This distance puts the phone out of easy reach, while the placement makes using it require moving the stick.

Keep your pocket notebook and a pen with you. If something occurs to you during the session that you would normally search for on your phone, jot it down and return to what you were doing. You can follow up on the notes when you decide to make time for them.

At that location, press **A** on the review screen to start or **B** to go back. Keep the stick in position during the opening sound and calibration, then leave it there throughout the focus session. Place it on the phone before starting, rather than moving it once the timer is running.

The display turns off automatically. Pressing either button during focus records a **peek** and briefly shows progress. Moving the stick enough to trigger the detector before completion ends the session with a breach alert and no harvest XP.

At the deadline, the successful event is saved locally and the display goes dark. **There is no automatic harvest sound, animation, or network request.** A brief green LED pulse every three seconds signals that the harvest is saved and you can safely move the stick. The LED stops when you reveal the reward. When you press either button or move the stick, it reveals the plant, plays the reward sounds, and attempts synchronization. That interaction is not counted as a peek or a breach.

| State | Button A | Button B | Movement |
| --- | --- | --- | --- |
| Garden | Review selected intention | Next intention | Wake the display |
| Review | Start session | Back to garden | Wake the display |
| Focus | Peek at progress | Peek at progress | May trigger a breach |
| Completed, awaiting your return | Reveal harvest | Reveal harvest | Reveal harvest |

### Offline use and battery

Sessions can run without a server connection. Outcomes are stored in `pending_sync.json`; failed sends remain queued, and startup attempts to deliver older queued events. A successful harvest attempts its own send when you reveal it.

If synchronization fails, the stick shows **SAVED OFFLINE** with diagnostic details. Press A or B to continue; the screen also times out. Restart with the server reachable to retry the queue.

The battery is checked once per minute. At **15% or below**, a short tone and a four-second banner warn you, including during focus. The warning does not repeat until a reading reaches 20% or the application restarts.

## Updating and configuration

Before an update, back up the device's `config.py`, `wifi_credentials.json`, and `pending_sync.json`. Upload `apps/`, `libs/`, and `res/` together, merge any new configuration options, then restart the stick. Keep the saved credentials and pending events.

If you are upgrading from **Farphone**, also update the device's existing `main.py` to launch `apps/tamarix.py` using the line shown above. Uploading the new file alone will leave an older `main.py` launching `apps/farphone.py` if that file is still on the stick. Saved Wi-Fi credentials and pending session events do not need to be renamed. The temporary setup network now appears as `Tamarix-xxxx`.

Defaults in `config.py`:

```python
BACKEND_URL = ""               # Fallback; the address saved during setup wins
LIGHT_SLEEP_ENABLED = True
HARVEST_TIMING_SCREEN = False
SERIAL_LOG_ENABLED = False
LOW_BATTERY_PERCENT = 15
```

Keep serial logging disabled for normal battery operation. For a USB debugging session, temporarily disable light sleep and enable serial logging; restore the defaults afterward. Light sleep can interrupt the Thonny USB connection.

Wi-Fi credentials are stored unencrypted on the device. Do not include your `wifi_credentials.json` when sharing a copy of the project.

## Current prototype boundaries

- The backend and account management are separate from this repository; the firmware retains a fixed test identity.
- Only a session event is persisted at quiet completion. If the stick restarts before you reveal it, the event remains queued, but its animation is not replayed.
- Older queued events are retried at startup. There is no periodic background queue retry, despite the legacy `SYNC_INTERVAL_MS` setting.
- Offline storage holds up to 500 events. A corrupt or full queue produces a storage error rather than silently discarding sessions.
- The firmware sends no `timestamp`; the server assigns it when the POST arrives. Offline delivery therefore does not preserve the original completion time on the server.
- Delivery is not guaranteed to be exactly once if a server response is lost after accepting an event.
- Peek counts, first-peek timing, and motion-triggered failures describe interactions with the stick. Their use as behavioral or clinical research measures has not been validated.
- The UI uses readable medieval-style English; technical errors retain plain English.

## Development and troubleshooting

Run the host-side tests from the repository root:

```sh
python3 -B -m unittest discover -s tests -q
```

Tests simulate hardware and network behavior. Verify motion, audio, QR scanning, and power consumption on a real StickS3.

Motion detection uses a filtered acceleration threshold of 0.04 g sustained
for 100 ms, or a tilt of 0.0175 radians (about 1 degree) from
the starting position. The gravity filter uses alpha=0.95 to retain more of slow
acceleration changes. The duration requirement rejects isolated acceleration
spikes; tilt detection remains immediate. Vibrations may still end a session.
Check gentle pickup and
stationary behavior on the device. Very slow, level transfers can still go
undetected because the accelerometer does not measure contact with the phone.

| Symptom | Check |
| --- | --- |
| Missing module or unexpected argument error | Upload the complete application from one revision and restart. Check the directory layout above. |
| Phone says the setup network has no Internet | Stay connected; it is a local configuration network. |
| Saved offline / sync failed | Note the on-device error details. Check the Wi-Fi, server address, server availability, and network access. |
| Thonny loses its connection | Reconnect with Stop/Restart; temporarily disable light sleep for serial debugging. |
| Storage error | Back up `pending_sync.json` before investigating. Do not clear it to hide the error. |

Further details: [Wi-Fi setup](wifi-setup.md) · [Firmware reliability and device checks](firmware-reliability.md).


### The Severing of the Bough

A broken pact is presented as a solemn withdrawal: an ash-grey sprout freezes,
fractures into rising pixel dust, then gives way to a single edict:
“Thou hast sought the mire. The sap withdraws into the deep.”
The former whistle is replaced by quiet descending tones (880 Hz for 500 ms,
622 Hz for 900 ms, then a 311 Hz pulse for 40 ms, speaker volume 120).
Audio shuts down before two seconds of display blackout. The outcome is saved
locally before the rite; network synchronization follows the rite and then the
stick returns to idle. Verify volume and legibility on
actual hardware.
