# Wi-Fi setup from your phone

On first boot, when no credentials have been saved:

1. The stick displays a **Wi-Fi QR code**. Scan it with your phone’s camera and accept the connection to the temporary `Tamarix-xxxx` network. No password typing is needed on supported phones. If your phone reports no Internet connection, choose to stay connected.
2. Once connected, press **B** on the stick to display the second QR code. Scan it to open **http://192.168.4.1**, the configuration page. Joining Wi-Fi and opening the page are two separate steps.
3. Press **B** again for manual instructions showing the network name, temporary password, and browser address. Another press returns to the Wi-Fi QR. If QR drawing is unavailable in the installed firmware, manual instructions appear automatically. Pages stay still until B is pressed; A exits setup and the three-minute timeout still applies.
4. Select your **2.4 GHz** home network from **Reti Wi-Fi disponibili** and enter its password. Networks are scanned once when setup opens, sorted by signal strength, and duplicate names are removed (up to 30 names). For a hidden or missing network, expand **Rete nascosta o non presente?** and enter the exact name manually; this overrides the dropdown selection. If the scan fails or finds no networks, manual entry remains available. To refresh the list, exit and reopen setup on the stick. Personal and open networks are supported; enterprise authentication and networks requiring a captive portal login are not.
5. Enter the **server address** in **Indirizzo del server**, for example `http://192.168.178.45:8080`. Use HTTP and an optional port, without paths, query parameters, or credentials. HTTPS is not supported by the current client. The server must be reachable from the stick’s Wi-Fi network.
6. Press **Collega lo stick** (“Connect the stick”) and wait for **Wi-Fi salvato!** (“Wi-Fi saved!”) on the stick. Your phone may disconnect during the channel change: use the message on the device to confirm the result.
7. Reconnect your phone to its usual network. The stick continues with normal synchronization.

To change networks, restart the stick and press **B** when prompted, within the first two seconds of the prompt appearing. The previous Wi-Fi credentials and server address are kept until the new Wi-Fi connection and save both succeed. The setup validates the server URL format; it does not test server availability. Normal synchronization runs after setup. A temporarily unreachable router does not automatically open setup.

Press **A** to skip setup. Setup times out after three minutes, with a possible short delay if a request is in progress. The temporary network is also shut down if an error occurs. Buttons are checked every 100 ms during a connection attempt; while receiving an HTTP request, responding to button A may take a few seconds.

## Installation with Thonny

Copy `apps/tamarix.py`, `libs/frontend/ui_renderer.py`, `libs/network/network_client.py`, and the new `libs/network/wifi_credentials.py` and `libs/network/wifi_setup.py` to the same paths on the device. `config.py` no longer requires an SSID or password; keep your power settings. The server URL saved through phone setup takes priority over `BACKEND_URL`. That setting remains a fallback for older saved configurations. Press B during boot to enter the URL through setup; if neither source has a URL, setup opens automatically. The old `WIFI_SSID` and `WIFI_PASSWORD` values are ignored if they are still present.

Wi-Fi credentials and the server URL (`backend_url`) are written to `wifi_credentials.json` on the device filesystem using a temporary file and a rename operation. The file is not encrypted at rest: anyone with filesystem access can read it. Both credential files are excluded from Git; do not include them in distributed firmware. The temporary access point password is random and changes each time setup opens. Home network credentials are neither printed to logs nor displayed in the web response.

## Verification on the StickS3

Host tests simulate the filesystem, HTTP requests, and radios; they do not verify the specific UIFlow build installed on the device or phone behavior.

- QR codes: scan both codes on the physical display using iPhone/Android; confirm the first joins the temporary network and the second opens the form. Check B cycles through both QR codes and manual details, and A still exits.
- First boot: connect using an iPhone or Android phone, enter the correct password, restart, and synchronize without setup.
- Server URL: reject invalid or HTTPS URLs without replacing the saved settings; confirm the saved URL is used after restart even when `config.py` contains a different URL.
- Network scan: verify the dropdown lists nearby networks, selecting a network connects correctly, and manual entry works for hidden networks.
- Incorrect password: an error message appears and the user can retry.
- Failed network change: the previous credentials remain valid after a restart.
- Button A and timeout: the app resumes and the access point is no longer visible.
- After setup: focus, peek, motion alerts, and light sleep remain operational.
- Unreachable backend: Wi-Fi credentials are saved, but the profile is offline; credentials are not lost.

The access point uses `network.WLAN(AP_IF)` and WPA2, with parameter names compatible with ESP32/UIFlow and a fallback for newer APIs. If the firmware does not support protected setup, setup exits: no page is served over an open network.

API reference: https://docs.micropython.org/en/v1.24.0/library/network.WLAN.html

QR rendering API: https://uiflow-micropython.readthedocs.io/en/2.4.5/hardware/display.html

Wi-Fi QR format: https://github.com/zxing/zxing/wiki/Barcode-Contents#wi-fi-network-config-android-ios-11
