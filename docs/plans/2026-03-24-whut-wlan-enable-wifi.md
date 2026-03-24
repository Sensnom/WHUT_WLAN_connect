# WHUT-WLAN Enable Wi-Fi Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `login.py` enable the Linux Wi-Fi radio before switching to `WHUT-WLAN`, while also handling missing command-line arguments cleanly.

**Architecture:** Keep the workflow in `login.py` so the script remains a single entrypoint. Add one small `nmcli radio wifi on` helper, validate CLI arguments early, and update `ensure_wifi_connected()` so radio enable always happens before SSID detection and connection.

**Tech Stack:** Python 3, `requests`, `unittest`, Linux `nmcli` / NetworkManager

---

### Task 1: Add a failing test for missing arguments

**Files:**
- Modify: `tests/test_login.py`
- Modify: `login.py`

**Step 1: Write the failing test**

Add a test like:

```python
def test_main_returns_usage_error_when_args_missing(self):
    with mock.patch("login.heading"):
        with mock.patch("login.logging.error") as log_error:
            exit_code = login.main(["login.py"])

    self.assertEqual(exit_code, 1)
    log_error.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_login.LoginWifiHelpersTest.test_main_returns_usage_error_when_args_missing`
Expected: FAIL with `IndexError` or wrong return value.

**Step 3: Write minimal implementation**

Update `main(argv)` in `login.py`:

```python
def main(argv):
    heading()
    if len(argv) < 3:
        logging.error("usage: python3 login.py <username> <password>")
        return 1
    username = argv[1]
    password = argv[2]
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_login.LoginWifiHelpersTest.test_main_returns_usage_error_when_args_missing`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_login.py login.py
git commit -m "fix: handle missing login arguments"
```

### Task 2: Add a failing test for enabling the Wi-Fi radio

**Files:**
- Modify: `tests/test_login.py`
- Modify: `login.py`

**Step 1: Write the failing test**

Add tests like:

```python
def test_enable_wifi_radio_raises_on_nmcli_error(self):
    result = subprocess.CompletedProcess(
        args=["nmcli"], returncode=1, stdout="", stderr="Wi-Fi blocked"
    )
    with mock.patch("login.run_nmcli_command", return_value=result):
        with self.assertRaises(RuntimeError):
            login.enable_wifi_radio()

def test_ensure_wifi_connected_enables_wifi_first(self):
    with mock.patch("login.ensure_nmcli_available"):
        with mock.patch("login.enable_wifi_radio") as enable_wifi_radio:
            with mock.patch("login.get_current_wifi_ssid", return_value="Other"):
                with mock.patch("login.connect_wifi") as connect_wifi:
                    login.ensure_wifi_connected("WHUT-WLAN")

    enable_wifi_radio.assert_called_once_with()
    connect_wifi.assert_called_once_with("WHUT-WLAN")
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_login.LoginWifiHelpersTest.test_enable_wifi_radio_raises_on_nmcli_error tests.test_login.LoginWifiHelpersTest.test_ensure_wifi_connected_enables_wifi_first`
Expected: FAIL because `enable_wifi_radio` does not exist or is not called.

**Step 3: Write minimal implementation**

Add to `login.py`:

```python
def enable_wifi_radio():
    result = run_nmcli_command(["radio", "wifi", "on"])
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown nmcli error"
        raise RuntimeError(f"failed to enable wifi: {message}")
```

And update:

```python
def ensure_wifi_connected(target_ssid):
    ensure_nmcli_available()
    enable_wifi_radio()
    current_ssid = get_current_wifi_ssid()
    ...
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_login.LoginWifiHelpersTest.test_enable_wifi_radio_raises_on_nmcli_error tests.test_login.LoginWifiHelpersTest.test_ensure_wifi_connected_enables_wifi_first`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_login.py login.py
git commit -m "feat: enable wifi before ssid switching"
```

### Task 3: Verify startup failure reporting stays readable

**Files:**
- Modify: `tests/test_login.py`
- Modify: `login.py` if needed

**Step 1: Write the failing test**

Reuse or refine the existing startup failure test so it covers Wi-Fi enable failures:

```python
def test_main_returns_error_when_wifi_setup_fails(self):
    with mock.patch("login.heading"):
        with mock.patch(
            "login.ensure_wifi_connected",
            side_effect=RuntimeError("failed to enable wifi: Wi-Fi blocked"),
        ):
            with mock.patch("login.logging.exception") as log_exception:
                exit_code = login.main(["login.py", "20240001", "secret"])

    self.assertEqual(exit_code, 1)
    log_exception.assert_called_once()
```

**Step 2: Run test to verify behavior**

Run: `python3 -m unittest tests.test_login.LoginWifiHelpersTest.test_main_returns_error_when_wifi_setup_fails`
Expected: PASS if current logging is already correct, otherwise FAIL and then adjust.

**Step 3: Write minimal implementation if needed**

If the message is too vague, keep this structure:

```python
except Exception:
    logging.exception("startup failed")
    return 1
```

**Step 4: Run focused test again**

Run: `python3 -m unittest tests.test_login.LoginWifiHelpersTest.test_main_returns_error_when_wifi_setup_fails`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_login.py login.py
git commit -m "fix: keep wifi startup failures readable"
```

### Task 4: Run final verification and refresh docs

**Files:**
- Modify: `README.md`

**Step 1: Write the failing documentation expectation**

Manual expectation: README should say the script now turns Wi-Fi on, then connects to `WHUT-WLAN`, then logs in.

**Step 2: Update documentation**

Add a short note to `README.md` explaining:

- Linux requires `nmcli`
- the script will turn Wi-Fi on automatically
- then it will connect to `WHUT-WLAN`

**Step 3: Run full verification**

Run: `python3 -m py_compile login.py tests/test_login.py && python3 -m unittest tests/test_login.py`
Expected: syntax check passes, all tests pass.

**Step 4: Run manual verification**

Run: `python3 login.py <username> <password>` with Wi-Fi turned off.
Expected: Wi-Fi turns on, switches to `WHUT-WLAN`, then attempts portal login.

**Step 5: Commit**

```bash
git add README.md login.py tests/test_login.py
git commit -m "docs: document automatic wifi enabling"
```
