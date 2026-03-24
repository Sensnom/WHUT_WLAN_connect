import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import install_autostart


class InstallAutostartHelpersTest(unittest.TestCase):
    def test_build_env_file_content(self):
        content = install_autostart.build_env_file_content("20240001", "secret")

        self.assertIn("WHUT_USERNAME=20240001\n", content)
        self.assertIn("WHUT_PASSWORD=secret\n", content)

    def test_build_env_file_content_quotes_special_characters(self):
        content = install_autostart.build_env_file_content("user name", 'p"a ss\\word')

        self.assertIn('WHUT_USERNAME="user name"\n', content)
        self.assertIn('WHUT_PASSWORD="p\\"a ss\\\\word"\n', content)

    def test_build_env_file_content_rejects_newlines(self):
        with self.assertRaises(RuntimeError):
            install_autostart.build_env_file_content("20240001", "bad\nsecret")

    def test_build_service_file_content_uses_detected_paths(self):
        content = install_autostart.build_service_file_content(
            python_path="/usr/bin/python3",
            project_dir="/tmp/WHUT-WLAN-main",
            env_path="/tmp/WHUT-WLAN-main/whut-wlan.env",
            login_script="/tmp/WHUT-WLAN-main/login.py",
        )

        self.assertIn('WorkingDirectory="/tmp/WHUT-WLAN-main"\n', content)
        self.assertIn(
            'EnvironmentFile="/tmp/WHUT-WLAN-main/whut-wlan.env"\n',
            content,
        )
        self.assertIn(
            'ExecStart="/usr/bin/python3" "/tmp/WHUT-WLAN-main/login.py"\n',
            content,
        )

    def test_build_service_file_content_escapes_paths_with_spaces(self):
        content = install_autostart.build_service_file_content(
            python_path="/tmp/My Project/.venv/bin/python",
            project_dir="/tmp/My Project",
            env_path="/tmp/My Project/whut-wlan.env",
            login_script="/tmp/My Project/login.py",
        )

        self.assertIn('WorkingDirectory="/tmp/My Project"\n', content)
        self.assertIn('EnvironmentFile="/tmp/My Project/whut-wlan.env"\n', content)
        self.assertIn(
            'ExecStart="/tmp/My Project/.venv/bin/python" "/tmp/My Project/login.py"\n',
            content,
        )

    def test_install_writes_env_and_service_files(self):
        with TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()
            user_systemd_dir = Path(tmp_dir) / "user-systemd"

            with mock.patch(
                "install_autostart.get_runtime_paths",
                return_value={
                    "project_dir": project_dir,
                    "env_path": project_dir / install_autostart.ENV_FILE_NAME,
                    "service_path": user_systemd_dir / install_autostart.SERVICE_NAME,
                    "login_script": project_dir / "login.py",
                    "python_path": Path("/usr/bin/python3"),
                },
            ):
                with mock.patch("install_autostart.run_systemctl_user_command"):
                    (project_dir / ".venv").mkdir()
                    (project_dir / ".venv/bin").mkdir()
                    (project_dir / ".venv/bin/python").write_text("", encoding="utf-8")
                    install_autostart.install_autostart("20240001", "secret")

            self.assertTrue((project_dir / install_autostart.ENV_FILE_NAME).exists())
            self.assertTrue(
                (user_systemd_dir / install_autostart.SERVICE_NAME).exists()
            )

    def test_install_runs_systemctl_user_commands(self):
        with TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()
            user_systemd_dir = Path(tmp_dir) / "user-systemd"

            with mock.patch(
                "install_autostart.get_runtime_paths",
                return_value={
                    "project_dir": project_dir,
                    "env_path": project_dir / install_autostart.ENV_FILE_NAME,
                    "service_path": user_systemd_dir / install_autostart.SERVICE_NAME,
                    "login_script": project_dir / "login.py",
                    "python_path": project_dir / ".venv/bin/python",
                },
            ):
                with mock.patch(
                    "install_autostart.run_systemctl_user_command"
                ) as run_command:
                    (project_dir / ".venv").mkdir()
                    (project_dir / ".venv/bin").mkdir()
                    (project_dir / ".venv/bin/python").write_text("", encoding="utf-8")
                    install_autostart.install_autostart("20240001", "secret")

        self.assertEqual(
            run_command.call_args_list,
            [
                mock.call(["daemon-reload"]),
                mock.call(["enable", "--now", install_autostart.SERVICE_NAME]),
            ],
        )

    def test_get_runtime_paths_uses_project_venv_python(self):
        with TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "Project Root"
            project_dir.mkdir()

            with mock.patch(
                "install_autostart.get_project_dir", return_value=project_dir
            ):
                paths = install_autostart.get_runtime_paths()

        self.assertEqual(paths["python_path"], project_dir / ".venv/bin/python")

    def test_install_autostart_raises_when_project_venv_missing(self):
        with TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()
            user_systemd_dir = Path(tmp_dir) / "user-systemd"

            with mock.patch(
                "install_autostart.get_runtime_paths",
                return_value={
                    "project_dir": project_dir,
                    "env_path": project_dir / install_autostart.ENV_FILE_NAME,
                    "service_path": user_systemd_dir / install_autostart.SERVICE_NAME,
                    "login_script": project_dir / "login.py",
                    "python_path": project_dir / ".venv/bin/python",
                },
            ):
                with self.assertRaises(RuntimeError):
                    install_autostart.install_autostart("20240001", "secret")

    def test_run_systemctl_user_command_raises_readable_error_when_binary_missing(self):
        with mock.patch(
            "install_autostart.subprocess.run",
            side_effect=FileNotFoundError("systemctl"),
        ):
            with self.assertRaises(RuntimeError):
                install_autostart.run_systemctl_user_command(["daemon-reload"])

    def test_write_file_uses_0600_for_env_files(self):
        with TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / install_autostart.ENV_FILE_NAME

            install_autostart.write_file(env_path, "WHUT_USERNAME=test\n", mode=0o600)

            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_uninstall_removes_service_and_reloads_systemd(self):
        with TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()
            env_path = project_dir / install_autostart.ENV_FILE_NAME
            env_path.write_text("secret", encoding="utf-8")
            service_path = (
                Path(tmp_dir) / "user-systemd" / install_autostart.SERVICE_NAME
            )
            service_path.parent.mkdir(parents=True)
            service_path.write_text("unit", encoding="utf-8")

            with mock.patch(
                "install_autostart.get_runtime_paths",
                return_value={
                    "project_dir": project_dir,
                    "env_path": env_path,
                    "service_path": service_path,
                    "login_script": project_dir / "login.py",
                    "python_path": project_dir / ".venv/bin/python",
                },
            ):
                with mock.patch(
                    "install_autostart.run_systemctl_user_command"
                ) as run_command:
                    install_autostart.uninstall_autostart()

        self.assertFalse(service_path.exists())
        self.assertEqual(
            run_command.call_args_list,
            [
                mock.call(["disable", "--now", install_autostart.SERVICE_NAME]),
                mock.call(["daemon-reload"]),
            ],
        )

    def test_uninstall_keeps_env_file(self):
        with TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()
            env_path = project_dir / install_autostart.ENV_FILE_NAME
            env_path.write_text("secret", encoding="utf-8")
            service_path = (
                Path(tmp_dir) / "user-systemd" / install_autostart.SERVICE_NAME
            )

            with mock.patch(
                "install_autostart.get_runtime_paths",
                return_value={
                    "project_dir": project_dir,
                    "env_path": env_path,
                    "service_path": service_path,
                    "login_script": project_dir / "login.py",
                    "python_path": project_dir / ".venv/bin/python",
                },
            ):
                with mock.patch(
                    "install_autostart.run_systemctl_user_command"
                ) as run_command:
                    install_autostart.uninstall_autostart()

            self.assertTrue(env_path.exists())
            run_command.assert_has_calls(
                [
                    mock.call(["disable", "--now", install_autostart.SERVICE_NAME]),
                    mock.call(["daemon-reload"]),
                ]
            )

    def test_uninstall_ignores_missing_service_on_disable(self):
        with TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "project"
            project_dir.mkdir()
            env_path = project_dir / install_autostart.ENV_FILE_NAME
            env_path.write_text("secret", encoding="utf-8")
            service_path = (
                Path(tmp_dir) / "user-systemd" / install_autostart.SERVICE_NAME
            )

            with mock.patch(
                "install_autostart.get_runtime_paths",
                return_value={
                    "project_dir": project_dir,
                    "env_path": env_path,
                    "service_path": service_path,
                    "login_script": project_dir / "login.py",
                    "python_path": project_dir / ".venv/bin/python",
                },
            ):
                with mock.patch(
                    "install_autostart.run_systemctl_user_command",
                    side_effect=[
                        RuntimeError("Unit whut-wlan.service not loaded."),
                        None,
                    ],
                ) as run_command:
                    install_autostart.uninstall_autostart()

            run_command.assert_has_calls(
                [
                    mock.call(["disable", "--now", install_autostart.SERVICE_NAME]),
                    mock.call(["daemon-reload"]),
                ]
            )

    def test_run_systemctl_user_command_raises_on_failure(self):
        result = subprocess.CompletedProcess(
            args=["systemctl", "--user"],
            returncode=1,
            stdout="",
            stderr="Failed to connect to bus",
        )

        with mock.patch("install_autostart.subprocess.run", return_value=result):
            with self.assertRaises(RuntimeError):
                install_autostart.run_systemctl_user_command(["daemon-reload"])


if __name__ == "__main__":
    unittest.main()
