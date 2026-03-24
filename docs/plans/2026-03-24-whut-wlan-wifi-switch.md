# WHUT-WLAN Wi-Fi Switch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `login.py` switch the Linux Wi-Fi connection to `WHUT-WLAN` with `nmcli` before attempting the existing campus portal login.

**Architecture:** Keep everything in `login.py` to preserve the current one-command workflow. Add a small `subprocess`-based Wi-Fi management layer that verifies `nmcli`, inspects the active SSID, connects to `WHUT-WLAN` when needed, and aborts early on Wi-Fi errors so the existing login path only runs in the correct network context.

**Tech Stack:** Python 3, `requests`, Linux `nmcli` / NetworkManager, manual runtime verification

---

### Task 1: Add Wi-Fi command helpers

**Files:**
- Modify: `login.py`

**Step 1: Write the failing test**

There is no test suite in this repository. For this small script, create a manual verification target instead: running the script on Linux should no longer raise `NameError` or import errors when Wi-Fi helper functions are added.

**Step 2: Run a syntax check to verify the current baseline**

Run: `python3 -m py_compile login.py`
Expected: PASS with no output.

**Step 3: Write minimal implementation**

In `login.py`, add:

```python
import shutil
import subprocess

TARGET_WIFI_SSID = "WHUT-WLAN"

def ensure_nmcli_available():
    if shutil.which("nmcli") is None:
        raise RuntimeError("nmcli not found; please install or enable NetworkManager")

def run_nmcli_command(args):
    return subprocess.run(
        ["nmcli", *args],
        check=False,
        capture_output=True,
        text=True,
    )
```

**Step 4: Run syntax check again**

Run: `python3 -m py_compile login.py`
Expected: PASS with no output.

**Step 5: Commit**

```bash
git add login.py
git commit -m "feat: add nmcli helper functions"
```

### Task 2: Detect the current Wi-Fi SSID

**Files:**
- Modify: `login.py`

**Step 1: Write the failing test**

Define expected manual behavior: when already connected to `WHUT-WLAN`, the script should identify that SSID and avoid reconnecting.

**Step 2: Add the minimal implementation**

In `login.py`, add a helper like:

```python
def get_current_wifi_ssid():
    result = run_nmcli_command(["-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        if line.startswith("yes:"):
            return line.split(":", 1)[1].strip()
    return ""
```

**Step 3: Run syntax check**

Run: `python3 -m py_compile login.py`
Expected: PASS with no output.

**Step 4: Run a quick manual probe on Linux**

Run: `python3 -c "import login; print(login.get_current_wifi_ssid())"`
Expected: prints the active SSID or a blank line without crashing.

**Step 5: Commit**

```bash
git add login.py
git commit -m "feat: detect active wifi ssid"
```

### Task 3: Add Wi-Fi connection logic

**Files:**
- Modify: `login.py`

**Step 1: Write the failing test**

Define expected manual behavior: if the current SSID is not `WHUT-WLAN`, the script should attempt `nmcli dev wifi connect WHUT-WLAN` and stop with a readable error on failure.

**Step 2: Write minimal implementation**

Add functions like:

```python
def connect_wifi(target_ssid):
    result = run_nmcli_command(["dev", "wifi", "connect", target_ssid])
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown nmcli error"
        raise RuntimeError(f"failed to connect to {target_ssid}: {message}")

def ensure_wifi_connected(target_ssid):
    ensure_nmcli_available()
    current_ssid = get_current_wifi_ssid()
    if current_ssid == target_ssid:
        logging.info("already connected to %s", target_ssid)
        return
    logging.info("switching wifi to %s", target_ssid)
    connect_wifi(target_ssid)
    time.sleep(3)
```

**Step 3: Run syntax check**

Run: `python3 -m py_compile login.py`
Expected: PASS with no output.

**Step 4: Run manual connection verification**

Run: `python3 login.py <username> <password>` while connected to another SSID.
Expected: logs Wi-Fi switching first, then proceeds to portal login.

**Step 5: Commit**

```bash
git add login.py
git commit -m "feat: connect to whut-wlan before login"
```

### Task 4: Integrate Wi-Fi switching into the main flow

**Files:**
- Modify: `login.py`
- Modify: `README.md`

**Step 1: Write the failing test**

Define expected manual behavior: every run of `login.py` should enforce the target SSID before calling the existing login request logic.

**Step 2: Write minimal implementation**

Update `__main__` in `login.py` to call:

```python
ensure_wifi_connected(TARGET_WIFI_SSID)
login_request(username, password)
```

Update `README.md` to mention the Linux `nmcli` requirement and the new run behavior.

**Step 3: Run syntax check**

Run: `python3 -m py_compile login.py`
Expected: PASS with no output.

**Step 4: Run full manual verification**

Run these scenarios:

- `python3 login.py <username> <password>` while on another SSID
- `python3 login.py <username> <password>` while already on `WHUT-WLAN`

Expected:

- first case switches Wi-Fi then logs in
- second case skips switching and logs in directly

**Step 5: Commit**

```bash
git add login.py README.md
git commit -m "feat: switch to whut-wlan before portal auth"
```

### Task 5: Verify failure handling

**Files:**
- Modify: `login.py` if needed after validation

**Step 1: Write the failing test**

Define expected manual behavior: failures from missing `nmcli` or unavailable `WHUT-WLAN` should exit clearly without attempting silent fallback.

**Step 2: Run failure-path verification**

Manual checks:

- Run on a system without `nmcli` in `PATH`
- Run where `WHUT-WLAN` is not visible

Expected:

- readable `RuntimeError` or logged error for missing `nmcli`
- readable `RuntimeError` or logged error for connection failure

**Step 3: Apply minimal fixes if output is confusing**

If needed, adjust exception handling in `__main__` so Wi-Fi failures log cleanly and stop execution.

Example target structure:

```python
try:
    ensure_wifi_connected(TARGET_WIFI_SSID)
    login_request(username, password)
except Exception:
    logging.exception("startup failed")
    sys.exit(1)
```

**Step 4: Re-run syntax check**

Run: `python3 -m py_compile login.py`
Expected: PASS with no output.

**Step 5: Commit**

```bash
git add login.py
git commit -m "fix: improve wifi setup failure reporting"
```
