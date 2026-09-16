# Farphone 🌱

**Put your phone aside. Give your life room to grow.**

Farphone is a small physical companion for digital wellbeing, built for the **M5Stack StickS3**. Place your phone face down with the stick resting on its back, as far away from you as possible, choose an intention, and spend time on something you want to nurture. A completed session grows a plant and earns XP for your garden.

The stick runs a MicroPython application on **UIFlow2**. This repository contains its firmware application, sounds, plant catalogue, and tests. The Spring Boot backend is a separate project.

## A garden for your attention

Attention is the soil from which our days grow. It nourishes a conversation, a meal, a night's rest, a new skill, and the quiet work of understanding ourselves.

Habitual scrolling can feel like a climbing vine: almost unnoticed at first, then winding through the spaces we meant to leave for other things. With our eyes on the phone, we can stop listening to ourselves and to the people and world around us. The feed's algorithms choose what appears next; following along can leave us alienated, with our attention at the mercy of those choices. Farphone invites you to loosen that grip and decide what receives your care.

Carry a pocket notebook as part of that choice. When the urge to look something up appears, write down the curiosity, question, or research idea instead: "How long does a platypus live?" A quick search can turn into tens of minutes swinging from app to app or reel to reel, like a monkey moving between vines. The notebook keeps the thought safe until you choose to explore it later, without giving the impulse your attention right now.

Each seed represents a part of life worth tending. Some grow inward, through rest and reflection. Others grow outward, through making things, learning, and being present with the people around us. Together, they form a garden that extends beyond the individual.

The reward can wait. When your session ends, Farphone saves your harvest quietly. The screen, sound, and synchronization appear only when you return to the stick. Stay with your book, your work, or your conversation for as long as you like.

## Why a separate device?

Starting a focus session in a phone app often means unlocking the very device you are trying to put aside. That moment can expose notification badges and familiar paths into other apps. Farphone lets you choose an intention and check session progress on a dedicated device, without opening the phone's interface.

The hardware also makes the commitment physical. Leaving the phone and stick in another room adds a journey between an impulse and a check. Resting the stick on the phone means reaching for the phone will usually move the stick as well. During focus, the firmware compares accelerometer readings with the starting position; sufficient tilt or sustained movement ends the session, records a `FAILED` outcome, and awards no XP. This creates friction at the moment of choice without depending on phone app permissions or operating system limits.

The single-purpose stick runs the session locally, away from the phone's notifications and background app behavior. It records button peeks, including their count and the time of the first peek, and saves session outcomes for later synchronization. These are measures of interaction with Farphone; the stick does not measure phone screen time.

## What it does

- Seven intentions, each with its own duration and plant collection.
- Common, rare, and legendary harvests with different XP rewards.
- Motion detection that registers a broken focus session when the stick is picked up or moved sufficiently before the timer ends.
- Brief button peeks to check progress without ending the session.
- Persistent offline storage and synchronization with the backend.
- Wi-Fi and server setup from a phone, with QR codes and nearby network selection.
- Display timeout, reduced idle CPU frequency, light sleep, and Wi-Fi shutdown after synchronization.
- A brief low-battery warning at 15% or below.

The physical arrangement is central to Farphone: **lay your phone face down, place the stick on its back with the display facing up, and leave both as far from you as possible, ideally in another room**. Phone proximity is a major factor in how often we check it and how much screen time follows; distance makes an automatic check less convenient. Reaching for the phone also means moving the stick, making the impulse to check it a deliberate action that the motion detector can register. Farphone senses the stick's movement; it does not monitor apps or lock the phone's operating system.

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
| `res/` | `res/` | Plant catalogue and all four WAV files |
| `config.py` | `config.py` | Power, diagnostics, and configuration defaults |

The result should include:

```text
apps/
  farphone.py
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
config.py
```

**Upload the complete set from the same revision.** Updating only the entry point can leave incompatible modules on the device. The network client belongs at `libs/network/network_client.py`; an old `libs/network_client.py` is not part of this layout. Tests and documentation do not need to be uploaded.

### 3. Set the test identity and startup

The prototype currently uses a fixed `USER_ID` in `apps/farphone.py`. For synchronization, that ID must identify a user in your backend. There is no account registration or sign-in flow on the stick yet.

To launch manually, run this in Thonny's device shell from the filesystem root:

```python
exec(open("apps/farphone.py").read(), globals())
```

For automatic startup, back up any existing device `main.py`, then create a `main.py` at the device root containing that same line. This repository does not supply a `main.py` or replace UIFlow's `boot.py`.

Set UIFlow2's **Boot Option** to **Run main.py directly** using M5Burner's configuration interface, then restart. This startup mode is described in the [official device guide](https://docs.m5stack.com/en/uiflow2/sticks3/program). Farphone handles its own Wi-Fi setup.

#### Return to the UIFlow2 menu

To restore the menu, connect the stick by USB, open **Configure** in M5Burner, and change **Boot Option** to **Show startup menu and network setup**. Restart afterward. To resume Farphone autostart, select **Run main.py directly** again. Keep the original UIFlow `boot.py` intact.

The [current official UIFlow boot source](https://github.com/m5stack/uiflow-micropython/blob/master/m5stack/fs/user/boot.py) also documents a StickS3 shortcut: hold **A while powering on or resetting** to enter the startup menu. In that implementation, this saves the menu boot option, so restore the direct-run option afterward if you want automatic Farphone startup again. This shortcut has not been verified on this project's UIFlow2 2.4.5 installation; use M5Burner's configuration route if it does not work. Back up `main.py` before trying recovery shortcuts on older firmware.

### 4. Configure Wi-Fi and the server

On first launch, the stick opens setup automatically if its network or server address is missing.

1. Scan the first QR code to join the temporary `Farphone-xxxx` network. Accept staying connected even if your phone reports no Internet access.
2. Press **B** for the second QR code. Scan it to open the setup page at `http://192.168.4.1`.
3. Select your nearby **2.4 GHz** network and enter its password. Hidden networks can be entered manually.
4. Enter the backend's base address, such as `http://192.168.178.45:8080`. Use the server's reachable address, not `localhost`, and omit endpoint paths such as `/api/harvest`.
5. Submit with **Collega lo stick** and wait for **Wi-Fi salvato!** on the device. Reconnect your phone to its usual network.

The current client supports **HTTP**, without HTTPS. A server running on your computer must accept connections from the stick's network. The setup form checks the address format; it does not verify that the server is online.

Press **B** during the two-second startup prompt to change the network or server later. In setup, B cycles the QR codes and manual instructions; A exits. See the [full Wi-Fi setup guide](docs/wifi-setup.md) for supported networks and troubleshooting.

## Use Farphone

### Choose what to nurture

From the **GREENHOUSE** screen, press **B** to browse intentions and **A** to review one.

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
| Greenhouse | Review selected intention | Next intention | Wake the display |
| Review | Start session | Back to greenhouse | Wake the display |
| Focus | Peek at progress | Peek at progress | May trigger a breach |
| Completed, awaiting your return | Reveal harvest | Reveal harvest | Reveal harvest |

### Offline use and battery

Sessions can run without a server connection. Outcomes are stored in `pending_sync.json`; failed sends remain queued, and startup attempts to deliver older queued events. A successful harvest attempts its own send when you reveal it.

If synchronization fails, the stick shows **SAVED OFFLINE** with diagnostic details. Press A or B to continue; the screen also times out. Restart with the server reachable to retry the queue.

The battery is checked once per minute. At **15% or below**, a short tone and a four-second banner warn you, including during focus. The warning does not repeat until a reading reaches 20% or the application restarts.

## Updating and configuration

Before an update, back up the device's `config.py`, `wifi_credentials.json`, and `pending_sync.json`. Upload `apps/`, `libs/`, and `res/` together, merge any new configuration options, then restart the stick. Keep the saved credentials and pending events.

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
- The UI currently mixes English labels with some Italian setup text and plant names.

## Development and troubleshooting

Run the host-side tests from the repository root:

```sh
python3 -B -m unittest discover -s tests -q
```

Tests simulate hardware and network behavior. Verify motion, audio, QR scanning, and power consumption on a real StickS3.

| Symptom | Check |
| --- | --- |
| Missing module or unexpected argument error | Upload the complete application from one revision and restart. Check the directory layout above. |
| Phone says the setup network has no Internet | Stay connected; it is a local configuration network. |
| Saved offline / sync failed | Note the on-device error details. Check the Wi-Fi, server address, server availability, and network access. |
| Thonny loses its connection | Reconnect with Stop/Restart; temporarily disable light sleep for serial debugging. |
| Storage error | Back up `pending_sync.json` before investigating. Do not clear it to hide the error. |

Further details: [Wi-Fi setup](docs/wifi-setup.md) · [Firmware reliability and device checks](docs/firmware-reliability.md).
