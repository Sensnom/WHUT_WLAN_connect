# WHUT-WLAN Portable Autostart Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the project to `uv`-managed dependencies, harden the autostart installer for portability and secret safety, and add a one-command uninstall flow for the generated user service.

**Architecture:** Use `pyproject.toml` and a project-local `.venv` as the single source of truth for runtime dependencies. Keep service lifecycle management in `install_autostart.py`, extend it with safe env-file and systemd-unit generation plus `--uninstall`, and leave `login.py` focused on loading credentials and performing the existing Wi-Fi/login workflow.

**Tech Stack:** Python 3, `uv`, `requests`, `unittest`, Linux `systemd --user`, NetworkManager `nmcli`

---

### Task 1: Add failing tests for secure env-file and service generation

**Files:**
- Modify: `tests/test_install_autostart.py`
- Modify: `install_autostart.py`

**Step 1: Write the failing tests**

Add tests like:

```python
def test_build_env_file_content_quotes_special_characters(self):
    content = install_autostart.build_env_file_content("user name", 'p"a ss\\word')
    self.assertIn('WHUT_USERNAME="user name"\n', content)
    self.assertIn('WHUT_PASSWORD="p\\"a ss\\\\word"\n', content)

def test_build_env_file_content_rejects_newlines(self):
    with self.assertRaises(RuntimeError):
        install_autostart.build_env_file_content("20240001", "bad\nsecret")

def test_build_service_file_content_escapes_paths_with_spaces(self):
    content = install_autostart.build_service_file_content(
        python_path="/tmp/My Project/.venv/bin/python",
        project_dir="/tmp/My Project",
        env_path="/tmp/My Project/whut-wlan.env",
        login_script="/tmp/My Project/login.py",
    )
    self.assertIn('ExecStart="/tmp/My Project/.venv/bin/python" "/tmp/My Project/login.py"', content)
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_install_autostart.InstallAutostartHelpersTest.test_build_env_file_content_quotes_special_characters tests.test_install_autostart.InstallAutostartHelpersTest.test_build_env_file_content_rejects_newlines tests.test_install_autostart.InstallAutostartHelpersTest.test_build_service_file_content_escapes_paths_with_spaces -v`
Expected: FAIL because env quoting, validation, and service escaping are not implemented yet.

**Step 3: Write minimal implementation**

Implement helper functions that:

- encode env values for `EnvironmentFile=` with double quotes and escaping
- reject `\n`, `\r`, and `\0`
- quote service paths in generated unit content

**Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_install_autostart.InstallAutostartHelpersTest.test_build_env_file_content_quotes_special_characters tests.test_install_autostart.InstallAutostartHelpersTest.test_build_env_file_content_rejects_newlines tests.test_install_autostart.InstallAutostartHelpersTest.test_build_service_file_content_escapes_paths_with_spaces -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_install_autostart.py install_autostart.py
git commit -m "fix: harden autostart file generation"
```

### Task 2: Add failing tests for uv runtime detection and clearer systemctl errors

**Files:**
- Modify: `tests/test_install_autostart.py`
- Modify: `install_autostart.py`

**Step 1: Write the failing tests**

Add tests like:

```python
def test_get_runtime_paths_uses_project_venv_python(self):
    ...

def test_install_autostart_raises_when_project_venv_missing(self):
    ...

def test_run_systemctl_user_command_raises_readable_error_when_binary_missing(self):
    ...
```

The runtime-path test should verify the interpreter path resolves to `.venv/bin/python` under the detected project root, not `sys.executable`.

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_install_autostart -v`
Expected: FAIL because the installer currently uses `sys.executable` and does not handle missing `systemctl` cleanly.

**Step 3: Write minimal implementation**

Update `install_autostart.py` so that:

- `get_runtime_paths()` points to `project_dir / ".venv/bin/python"`
- install fails with a readable `RuntimeError` if that interpreter is missing
- `run_systemctl_user_command()` catches `FileNotFoundError` and raises a readable `RuntimeError`

**Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_install_autostart -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_install_autostart.py install_autostart.py
git commit -m "feat: require uv-managed project runtime"
```

### Task 3: Add failing tests for uninstall behavior and secure file permissions

**Files:**
- Modify: `tests/test_install_autostart.py`
- Modify: `install_autostart.py`

**Step 1: Write the failing tests**

Add tests like:

```python
def test_write_file_uses_0600_for_env_files(self):
    ...

def test_uninstall_removes_service_and_reloads_systemd(self):
    ...

def test_uninstall_keeps_env_file(self):
    ...
```

The uninstall test should verify the script calls:

```python
["disable", "--now", install_autostart.SERVICE_NAME]
["daemon-reload"]
```

and deletes the service file when present.

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_install_autostart -v`
Expected: FAIL because uninstall flow and env-file permission handling are not implemented yet.

**Step 3: Write minimal implementation**

Implement:

- `write_file(..., mode=None)` with `0o600` for the env file
- uninstall function that disables/stops the user service, removes the unit file if it exists, and reloads `systemd`
- lenient behavior if the service file is already absent

**Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_install_autostart -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_install_autostart.py install_autostart.py
git commit -m "feat: add autostart uninstall flow"
```

### Task 4: Add uv project files and update repository hygiene

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock` if generated
- Modify: `.gitignore`

**Step 1: Write the failing expectation**

Manual expectation: the repo should support `uv sync`, create `.venv`, and avoid committing `whut-wlan.env` or `.venv/`.

**Step 2: Write minimal implementation**

Create `pyproject.toml` with project metadata and `requests` dependency. Update `.gitignore` to ignore:

- `.venv/`
- `whut-wlan.env`

Keep `uv.lock` tracked if generated.

**Step 3: Verify environment setup**

Run: `uv sync`
Expected: `.venv/` created and dependencies installed successfully.

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock .gitignore
git commit -m "build: manage project environment with uv"
```

### Task 5: Update docs and run full verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_login.py` if needed

**Step 1: Update documentation**

Document:

- install `uv`
- run `uv sync`
- install with `python3 install_autostart.py`
- uninstall with `python3 install_autostart.py --uninstall`
- credentials are stored in plaintext in `whut-wlan.env`
- the service is user-level and may require `loginctl enable-linger <user>` for pre-login startup

**Step 2: Run full automated verification**

Run: `python3 -m py_compile login.py install_autostart.py tests/test_login.py tests/test_install_autostart.py && python3 -m unittest tests/test_login.py tests/test_install_autostart.py`
Expected: syntax check passes and all tests pass.

**Step 3: Run environment verification**

Run: `uv sync`
Expected: succeeds and leaves a project-local `.venv`.

**Step 4: Run a manual service lifecycle smoke test**

Run: `python3 install_autostart.py --username <username> --password <password>`
Expected: `whut-wlan.env` and `~/.config/systemd/user/whut-wlan.service` are written, service is enabled, and the unit points to `.venv/bin/python`.

Run: `python3 install_autostart.py --uninstall`
Expected: user service is disabled and removed, `whut-wlan.env` remains.

**Step 5: Commit**

```bash
git add README.md login.py install_autostart.py tests/test_login.py tests/test_install_autostart.py pyproject.toml .gitignore uv.lock
git commit -m "docs: document uv-based autostart lifecycle"
```
