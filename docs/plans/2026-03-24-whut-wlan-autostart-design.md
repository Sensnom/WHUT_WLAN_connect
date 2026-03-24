# WHUT-WLAN Portable Autostart Design

## Goal

Let the project install and remove its own Linux autostart setup in a portable way, while using `uv` to manage the Python environment and using secure file generation for stored credentials.

## Why This Change Is Needed

The earlier installer direction solved automatic user and path detection, but it still had several gaps:

- credentials needed safer encoding and file permissions
- generated `systemd` units needed path-safe escaping
- missing `systemctl` needed clearer error reporting
- the project still described dependency setup with `pip`
- there was no one-command uninstall path

For this project, portability means more than detecting the current directory. It also means the generated service should keep working when the repo lives in paths with spaces, the runtime should come from a project-local virtual environment, and migration to another machine should only require `uv sync` and a single install command.

## Recommended Approach

Use `uv` for dependency and virtual environment management, keep autostart installation in `install_autostart.py`, and extend that script with `--uninstall` support.

The service should use the project-local interpreter at `.venv/bin/python`, which is created by `uv sync`. The installer should fail clearly when `.venv/bin/python` does not exist yet, because that means the environment has not been prepared. The same script should also support a one-command uninstall flow that disables the service, removes the generated user service file, reloads `systemd`, and leaves the environment file in place by default.

This keeps runtime and installation concerns separate, makes the Python interpreter deterministic across machines, and gives the project a complete install/uninstall lifecycle without requiring `sudo`.

## Alternatives Considered

### 1. `pyproject.toml` + `uv sync` + `install_autostart.py --uninstall` (recommended)

- Smallest change that still gives deterministic environments
- Single install script for both lifecycle actions
- Easy migration to another machine

### 2. `pyproject.toml` + `uv sync` + separate uninstall script

- Clearer separation of commands
- More files and more user-facing commands to remember

### 3. Installer automatically runs `uv sync`

- More one-click behavior
- Couples environment bootstrapping to service installation
- Harder failure handling when `uv` is absent or network access is unavailable

## Runtime and Install Flow

### Environment setup flow

1. User runs `uv sync` in the project root.
2. `uv` creates `.venv/` and installs dependencies from `pyproject.toml`.
3. The project-local interpreter becomes available at `.venv/bin/python`.

### Install flow

1. User runs `python3 install_autostart.py`.
2. The installer detects the project root from its own file path.
3. The installer resolves `.venv/bin/python` relative to that root.
4. If the interpreter is missing, the installer exits and tells the user to run `uv sync` first.
5. The installer collects credentials from flags or interactive prompts.
6. The installer validates that credentials do not contain unsupported control characters.
7. The installer writes `whut-wlan.env` with secure quoting and `0600` permissions.
8. The installer writes `~/.config/systemd/user/whut-wlan.service` with escaped paths.
9. The installer runs `systemctl --user daemon-reload`.
10. The installer runs `systemctl --user enable --now whut-wlan.service`.
11. The installer prints verification commands and secret-handling reminders.

### Uninstall flow

1. User runs `python3 install_autostart.py --uninstall`.
2. The installer runs `systemctl --user disable --now whut-wlan.service`.
3. The installer removes `~/.config/systemd/user/whut-wlan.service` if it exists.
4. The installer runs `systemctl --user daemon-reload`.
5. The installer keeps `whut-wlan.env` by default and tells the user where it is.

## Code Changes

### `pyproject.toml`

Add project metadata and dependencies so `uv sync` becomes the primary setup path.

Keep the dependency list minimal. For this repository, only `requests` is currently required.

### `install_autostart.py`

Expand the installer so it:

- detects the project root via `Path(__file__).resolve().parent`
- requires `.venv/bin/python` under the project root
- safely encodes env-file values for `systemd` `EnvironmentFile=`
- rejects credentials containing newline, carriage return, or NUL
- writes `whut-wlan.env` with `0600` permissions
- escapes service paths so directories with spaces still work
- catches missing `systemctl` and reports a readable error
- supports `--uninstall`
- preserves the env file during uninstall unless a future purge option is added

### `login.py`

Keep the earlier credential-loading behavior:

- CLI args first
- `WHUT_USERNAME` / `WHUT_PASSWORD` fallback

No new behavior is needed here beyond preserving compatibility with the generated env file.

### `.gitignore`

Ignore:

- `whut-wlan.env`
- `.venv/`
- `uv.lock` only if the project decides not to commit it; otherwise keep it tracked

For a small application like this, committing `uv.lock` is usually preferable for reproducibility.

### `README.md`

Update setup and lifecycle docs to explain:

- install `uv`
- run `uv sync`
- use `python3 install_autostart.py` to install
- use `python3 install_autostart.py --uninstall` to remove the service
- credentials are stored in plaintext in `whut-wlan.env`
- `whut-wlan.env` should not be committed or shared
- the service is a user-level `systemd` service, not guaranteed to start before login unless linger is enabled

## Error Handling

- Missing `.venv/bin/python`
  - print `uv sync` guidance and exit cleanly
- Missing `systemctl`
  - print that user-level `systemd` is required
- `systemctl --user` bus unavailable
  - preserve and show the command failure message
- Existing env file or service file
  - overwrite on install so reruns refresh paths after migration
- Uninstall when service is absent
  - treat as safe and continue removing local artifacts

## Testing Strategy

Automated tests:

1. env-file encoding rejects unsupported characters and safely quotes special characters
2. generated service content handles paths with spaces
3. installer reports a readable error when `.venv/bin/python` is missing
4. installer reports a readable error when `systemctl` is missing
5. uninstall flow disables the service, removes the unit file, and reloads `systemd`
6. existing `login.py` env-based credential fallback still passes

Manual tests:

1. run `uv sync`, then `python3 install_autostart.py`, and verify the service uses `.venv/bin/python`
2. place the repo in a directory with spaces and verify the generated service still works
3. run `python3 install_autostart.py --uninstall` and verify the unit file is removed while `whut-wlan.env` remains
4. optionally enable linger and verify behavior after reboot if true boot-time user service startup is desired
