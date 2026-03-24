# WHUT-WLAN Enable Wi-Fi Design

## Goal

When the user runs `python3 login.py <username> <password>` on Linux, the script should first turn on the Wi-Fi radio with `nmcli`, then switch to `WHUT-WLAN`, and finally continue the existing campus network authentication flow.

## Why This Change Is Needed

The current version can switch SSIDs only when the Wi-Fi radio is already enabled. If Wi-Fi is turned off, `nmcli dev wifi connect WHUT-WLAN` cannot complete the connection flow, so the script does not satisfy the expected "open Wi-Fi and connect automatically" behavior.

## Recommended Approach

Keep the logic inside `login.py` and add a dedicated Wi-Fi radio enable step before SSID detection.

This preserves the existing one-command workflow and keeps all Linux-specific networking behavior in one place. The change stays small: validate arguments, verify `nmcli`, enable Wi-Fi, ensure the target SSID, then run the current portal login code.

## Runtime Flow

1. User runs `python3 login.py <username> <password>`.
2. The script validates that username and password were provided.
3. The script prints the banner.
4. The script verifies that `nmcli` exists.
5. The script runs `nmcli radio wifi on`.
6. The script checks the active Wi-Fi SSID.
7. If not already on `WHUT-WLAN`, the script runs `nmcli dev wifi connect WHUT-WLAN`.
8. If Wi-Fi setup succeeds, the script continues with the existing portal authentication.
9. If Wi-Fi radio enable or SSID switching fails, the script logs a clear error and exits with code `1`.

## Code Changes

### `login.py`

Add:

- `enable_wifi_radio()`
  - Runs `nmcli radio wifi on`
  - Raises a readable `RuntimeError` when the command fails

- argument validation in `main(argv)`
  - Returns a usage error instead of raising `IndexError`

Adjust:

- `ensure_wifi_connected(target_ssid)`
  - Call `ensure_nmcli_available()`
  - Call `enable_wifi_radio()`
  - Then inspect the active SSID and connect if needed

### `tests/test_login.py`

Add tests for:

- missing arguments returning error code `1`
- Wi-Fi radio enable being called before SSID switching
- Wi-Fi radio enable failure surfacing a readable startup error

## Error Handling

- Missing credentials
  - Log `usage: python3 login.py <username> <password>` and return `1`
- Missing `nmcli`
  - Tell the user to install or enable NetworkManager
- `nmcli radio wifi on` fails
  - Explain that the adapter may be blocked by hardware switch, rfkill, or driver state
- Target SSID unavailable
  - Preserve the `nmcli` failure message

## Testing Strategy

Automated tests:

1. Missing args returns `1` and logs usage
2. `enable_wifi_radio()` raises on non-zero `nmcli` exit
3. `ensure_wifi_connected()` enables Wi-Fi before attempting connection

Manual tests:

1. Turn Wi-Fi off, run the script, verify it turns Wi-Fi on and connects to `WHUT-WLAN`
2. Leave Wi-Fi on and already connected to `WHUT-WLAN`, verify it skips reconnecting
3. Turn Wi-Fi off with hardware block or invalid adapter state, verify a readable error is shown
