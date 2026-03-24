# WHUT-WLAN Wi-Fi Switch Design

## Goal

When the user runs `python3 login.py <username> <password>` on Linux, the script should first switch the system Wi-Fi connection to `WHUT-WLAN` with `nmcli`, then continue the existing campus network authentication flow.

## Current Project Context

- `login.py` already performs campus network authentication against the WHUT portal.
- The project does not currently manage the local Wi-Fi interface.
- The target environment is Linux with NetworkManager and `nmcli` available.
- The desired trigger is manual: Wi-Fi switching should happen each time the script runs.

## Recommended Approach

Use a single-script approach inside `login.py`.

This keeps the project simple and matches the current user experience: one command, one file, one responsibility from the user's point of view. The new logic should add a small Linux-specific pre-check and connection step before the existing authentication logic starts.

## Runtime Flow

1. User runs `python3 login.py <username> <password>`.
2. The script prints the banner.
3. The script verifies that `nmcli` is installed.
4. The script checks the currently active Wi-Fi SSID.
5. If the current SSID is not `WHUT-WLAN`, the script runs `nmcli` to connect to `WHUT-WLAN`.
6. If Wi-Fi connection succeeds, the script continues with the existing authentication request.
7. If Wi-Fi connection fails, the script exits with a clear error instead of attempting portal login.

## Code Changes

### `login.py`

Add a small Wi-Fi management layer using `subprocess`.

Planned functions:

- `ensure_nmcli_available()`
  - Checks whether `nmcli` exists in `PATH`.
  - Raises or logs a clear error if NetworkManager tools are unavailable.

- `get_current_wifi_ssid()`
  - Reads the active connection from `nmcli`.
  - Returns the current SSID or an empty value when not connected on Wi-Fi.

- `connect_wifi(target_ssid)`
  - Runs `nmcli dev wifi connect <ssid>`.
  - Captures stdout/stderr so failures can be surfaced clearly.

- `ensure_wifi_connected(target_ssid)`
  - Compares the current SSID with `WHUT-WLAN`.
  - Skips reconnect if already on the target SSID.
  - Otherwise attempts a connection and waits briefly for the interface to settle.

### Main Flow Adjustment

In `__main__`, call Wi-Fi setup before `login_request(username, password)`.

This preserves the existing login code path while making the network context correct first.

## Error Handling

- `nmcli` missing
  - Show a message telling the user to install or enable NetworkManager.
- `WHUT-WLAN` not visible
  - Surface the `nmcli` failure text so the user can tell whether scanning or signal is the issue.
- Connection denied or profile issue
  - Report the exact `nmcli` error and stop.
- Already on `WHUT-WLAN`
  - Log that no Wi-Fi switch is needed.
- Wi-Fi connected but portal login fails
  - Keep the current authentication logging behavior.

## Testing Strategy

Manual verification is sufficient for this small script.

1. Start on another Wi-Fi network and run the script.
   - Expected: it switches to `WHUT-WLAN`, then attempts portal login.
2. Start already connected to `WHUT-WLAN` and run the script.
   - Expected: it skips the switch step and goes straight to login.
3. Run on a system without `nmcli`.
   - Expected: clear setup error.
4. Run where `WHUT-WLAN` is unavailable.
   - Expected: clear connection failure.

## Scope Guardrails

- No background daemon or auto-retry loop for Wi-Fi management.
- No multi-platform support in this change.
- No configuration file unless later needed.
- Keep credentials handling exactly as it works today.
