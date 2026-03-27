import argparse
import getpass
import subprocess
from pathlib import Path


SERVICE_NAME = "whut-wlan.service"
TIMER_NAME = "whut-wlan.timer"
ENV_FILE_NAME = "whut-wlan.env"
DEFAULT_TIMER_ON_BOOT_SEC = "30s"
DEFAULT_TIMER_ON_UNIT_ACTIVE_SEC = "10min"


def encode_env_value(value):
    if any(char in value for char in ("\n", "\r", "\0")):
        raise RuntimeError("credentials contain unsupported characters")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    needs_quotes = any(char.isspace() or char in '#"\\' for char in value)
    if needs_quotes:
        return f'"{escaped}"'
    return escaped


def escape_systemd_exec_arg(value):
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_env_file_content(username, password):
    return (
        f"WHUT_USERNAME={encode_env_value(username)}\n"
        f"WHUT_PASSWORD={encode_env_value(password)}\n"
    )


def normalize_systemd_path(value):
    return str(value).replace("\\", "\\\\").replace(" ", "\\x20")


def build_service_file_content(python_path, project_dir, env_path, login_script):
    return """[Unit]
Description=WHUT WLAN Auto Login
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={project_dir}
EnvironmentFile={env_path}
ExecStart={python_path} {login_script}
""".format(
        project_dir=normalize_systemd_path(project_dir),
        env_path=normalize_systemd_path(env_path),
        python_path=escape_systemd_exec_arg(python_path),
        login_script=escape_systemd_exec_arg(login_script),
    )


def build_timer_file_content(on_boot_sec=DEFAULT_TIMER_ON_BOOT_SEC, on_unit_active_sec=DEFAULT_TIMER_ON_UNIT_ACTIVE_SEC):
    return f"""[Unit]
Description=Run WHUT WLAN auto login periodically

[Timer]
OnBootSec={on_boot_sec}
OnUnitActiveSec={on_unit_active_sec}
Unit={SERVICE_NAME}
Persistent=true

[Install]
WantedBy=timers.target
"""


def get_project_dir():
    return Path(__file__).resolve().parent


def get_runtime_paths():
    project_dir = get_project_dir()
    user_systemd_dir = Path.home() / ".config/systemd/user"
    return {
        "project_dir": project_dir,
        "env_path": project_dir / ENV_FILE_NAME,
        "service_path": user_systemd_dir / SERVICE_NAME,
        "timer_path": user_systemd_dir / TIMER_NAME,
        "login_script": project_dir / "login.py",
        "python_path": project_dir / ".venv/bin/python",
    }


def write_file(path, content, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def run_systemctl_user_command(args):
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "systemctl not found; user-level systemd is required"
        ) from exc
    if result.returncode != 0:
        message = (
            result.stderr.strip() or result.stdout.strip() or "unknown systemctl error"
        )
        raise RuntimeError(f"systemctl --user {' '.join(args)} failed: {message}")
    return result


def install_autostart(username, password):
    paths = get_runtime_paths()
    if not paths["python_path"].exists():
        raise RuntimeError("project virtual environment not found; run 'uv sync' first")
    env_content = build_env_file_content(username, password)
    service_content = build_service_file_content(
        python_path=paths["python_path"],
        project_dir=paths["project_dir"],
        env_path=paths["env_path"],
        login_script=paths["login_script"],
    )
    timer_content = build_timer_file_content()

    write_file(paths["env_path"], env_content, mode=0o600)
    write_file(paths["service_path"], service_content)
    write_file(paths["timer_path"], timer_content)

    run_systemctl_user_command(["daemon-reload"])
    run_systemctl_user_command(["disable", "--now", SERVICE_NAME],)
    run_systemctl_user_command(["enable", "--now", TIMER_NAME])
    run_systemctl_user_command(["start", SERVICE_NAME])

    return paths


def uninstall_autostart():
    paths = get_runtime_paths()
    for unit_name in (TIMER_NAME, SERVICE_NAME):
        try:
            run_systemctl_user_command(["disable", "--now", unit_name])
        except RuntimeError as exc:
            if unit_name not in str(exc):
                raise
    for path_key in ("service_path", "timer_path"):
        if paths[path_key].exists():
            paths[path_key].unlink()
    run_systemctl_user_command(["daemon-reload"])
    return paths


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Install WHUT WLAN autostart service")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--uninstall", action="store_true")
    return parser.parse_args(argv)


def prompt_if_missing(username, password):
    if not username:
        username = input("WHUT username: ").strip()
    if not password:
        password = getpass.getpass("WHUT password: ").strip()
    if not username or not password:
        raise RuntimeError("username and password are required")
    return username, password


def main(argv=None):
    args = parse_args(argv)
    if args.uninstall:
        paths = uninstall_autostart()
        print(f"Removed service file: {paths['service_path']}")
        print(f"Removed timer file: {paths['timer_path']}")
        print(f"Kept env file: {paths['env_path']}")
        return 0
    username, password = prompt_if_missing(args.username, args.password)
    paths = install_autostart(username, password)
    print(f"Wrote env file: {paths['env_path']}")
    print(f"Wrote service file: {paths['service_path']}")
    print(f"Wrote timer file: {paths['timer_path']}")
    print(f"Verify with: systemctl --user status {TIMER_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
