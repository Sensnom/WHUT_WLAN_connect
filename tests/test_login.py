import os
import subprocess
import unittest
from unittest import mock

import login


class LoginWifiHelpersTest(unittest.TestCase):
    def test_ensure_nmcli_available_raises_when_missing(self):
        with mock.patch("login.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError):
                login.ensure_nmcli_available()

    def test_get_current_wifi_ssid_returns_active_ssid(self):
        result = subprocess.CompletedProcess(
            args=["nmcli"],
            returncode=0,
            stdout="yes:WHUT-WLAN\nno:Other\n",
            stderr="",
        )

        with mock.patch("login.run_nmcli_command", return_value=result):
            self.assertEqual(login.get_current_wifi_ssid(), "WHUT-WLAN")

    def test_connect_wifi_raises_on_nmcli_error(self):
        result = subprocess.CompletedProcess(
            args=["nmcli"],
            returncode=10,
            stdout="",
            stderr="No network with SSID 'WHUT-WLAN' found.",
        )

        with mock.patch("login.run_nmcli_command", return_value=result):
            with self.assertRaises(RuntimeError):
                login.connect_wifi("WHUT-WLAN")

    def test_ensure_wifi_connected_skips_reconnect_on_target_ssid(self):
        with mock.patch("login.ensure_nmcli_available") as ensure_nmcli:
            with mock.patch("login.enable_wifi_radio") as enable_wifi_radio:
                with mock.patch(
                    "login.get_current_wifi_ssid", return_value="WHUT-WLAN"
                ):
                    with mock.patch("login.connect_wifi") as connect_wifi:
                        login.ensure_wifi_connected("WHUT-WLAN")

        ensure_nmcli.assert_called_once_with()
        enable_wifi_radio.assert_called_once_with()
        connect_wifi.assert_not_called()

    def test_enable_wifi_radio_raises_on_nmcli_error(self):
        result = subprocess.CompletedProcess(
            args=["nmcli"],
            returncode=1,
            stdout="",
            stderr="Wi-Fi blocked",
        )

        with mock.patch("login.run_nmcli_command", return_value=result):
            with self.assertRaises(RuntimeError):
                login.enable_wifi_radio()

    def test_ensure_wifi_connected_enables_wifi_first(self):
        with mock.patch("login.ensure_nmcli_available"):
            with mock.patch("login.enable_wifi_radio") as enable_wifi_radio:
                with mock.patch("login.get_current_wifi_ssid", return_value="Other"):
                    with mock.patch("login.connect_wifi") as connect_wifi:
                        with mock.patch("login.time.sleep") as sleep:
                            login.ensure_wifi_connected("WHUT-WLAN")

        enable_wifi_radio.assert_called_once_with()
        connect_wifi.assert_called_once_with("WHUT-WLAN")
        sleep.assert_called_once_with(3)

    def test_ensure_wifi_connected_retries_after_initial_connect_failure(self):
        with mock.patch("login.ensure_nmcli_available"):
            with mock.patch("login.enable_wifi_radio"):
                with mock.patch("login.get_current_wifi_ssid", return_value="Other"):
                    with mock.patch(
                        "login.connect_wifi",
                        side_effect=[RuntimeError("network not ready"), None],
                    ) as connect_wifi:
                        with mock.patch("login.time.sleep") as sleep:
                            login.ensure_wifi_connected("WHUT-WLAN")

        self.assertEqual(connect_wifi.call_count, 2)
        sleep.assert_any_call(3)

    def test_parse_json_response_returns_none_for_non_json(self):
        response = mock.Mock()
        response.json.side_effect = ValueError("bad json")
        self.assertIsNone(login.parse_json_response(response))

    def test_extract_login_result_success_from_json(self):
        response = mock.Mock()
        response.apparent_encoding = "utf-8"
        response.text = '{"authCode":"ok","message":"认证成功"}'
        response.json.return_value = {"authCode": "ok", "message": "认证成功"}

        result = login.extract_login_result(response)

        self.assertTrue(result["success"])
        self.assertEqual(result["auth_code"], "ok")
        self.assertEqual(result["message"], "认证成功")

    def test_extract_login_result_failure_from_json(self):
        response = mock.Mock()
        response.apparent_encoding = "utf-8"
        response.text = '{"authCode":"bad","message":"密码错误"}'
        response.json.return_value = {"authCode": "bad", "message": "密码错误"}

        result = login.extract_login_result(response)

        self.assertFalse(result["success"])
        self.assertEqual(result["auth_code"], "bad")
        self.assertEqual(result["message"], "密码错误")

    def test_get_nas_id_raises_when_missing(self):
        response = mock.Mock()
        response.url = "http://example.com/no-nasid"
        with mock.patch.object(login.session, "get", return_value=response):
            with self.assertRaises(login.LoginError):
                login.get_nas_id()

    def test_get_csrf_token_raises_when_missing(self):
        response = mock.Mock()
        response.text = "{}"
        response.json.return_value = {}
        with mock.patch.object(login.session, "get", return_value=response):
            with self.assertRaises(login.LoginError):
                login.get_csrf_token()

    def test_login_request_returns_already_online(self):
        with mock.patch(
            "login.check_network_status",
            return_value={"online": True, "status_code": 200, "url": "https://www.baidu.com"},
        ):
            with mock.patch("login.get_host_ip", return_value="5.6.7.8"):
                result = login.login_request("20240001", "secret")

        self.assertEqual(result["status"], "already_online")
        self.assertEqual(result["host_ip"], "5.6.7.8")

    def test_login_request_returns_login_success(self):
        response = mock.Mock()
        response.text = '{"authCode":"ok","message":"认证成功","UserIpv4":"1.2.3.4"}'
        response.apparent_encoding = "utf-8"
        response.json.return_value = {
            "authCode": "ok",
            "message": "认证成功",
            "UserIpv4": "1.2.3.4",
        }

        with mock.patch(
            "login.check_network_status",
            side_effect=[
                {"online": False, "status_code": 302, "url": "http://portal", "error": None},
                {"online": True, "status_code": 200, "url": "https://www.baidu.com"},
            ],
        ):
            with mock.patch("login.log_out"):
                with mock.patch("login.get_nas_id", return_value="nas-1"):
                    with mock.patch("login.get_csrf_token", return_value="csrf-token"):
                        with mock.patch("login.get_host_ip", return_value="5.6.7.8"):
                            with mock.patch.object(
                                login.session, "post", return_value=response
                            ) as post:
                                result = login.login_request("20240001", "secret")

        self.assertEqual(result["status"], "login_success")
        self.assertEqual(result["auth_code"], "ok")
        self.assertEqual(result["nas_id"], "nas-1")
        self.assertEqual(result["user_ip"], "1.2.3.4")
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], login.LOGIN_API_URL)

    def test_login_request_returns_login_failed(self):
        response = mock.Mock()
        response.text = '{"authCode":"bad","message":"密码错误"}'
        response.apparent_encoding = "utf-8"
        response.json.return_value = {"authCode": "bad", "message": "密码错误"}

        with mock.patch(
            "login.check_network_status",
            return_value={"online": False, "status_code": 302, "url": "http://portal", "error": None},
        ):
            with mock.patch("login.log_out"):
                with mock.patch("login.get_nas_id", return_value="nas-1"):
                    with mock.patch("login.get_csrf_token", return_value="csrf-token"):
                        with mock.patch.object(login.session, "post", return_value=response):
                            result = login.login_request("20240001", "secret")

        self.assertEqual(result["status"], "login_failed")
        self.assertEqual(result["auth_code"], "bad")
        self.assertEqual(result["message"], "密码错误")

    def test_login_request_returns_login_uncertain(self):
        response = mock.Mock()
        response.text = '{"authCode":"ok","message":"认证成功","UserIpv4":"1.2.3.4"}'
        response.apparent_encoding = "utf-8"
        response.json.return_value = {
            "authCode": "ok",
            "message": "认证成功",
            "UserIpv4": "1.2.3.4",
        }

        with mock.patch(
            "login.check_network_status",
            side_effect=[
                {"online": False, "status_code": 302, "url": "http://portal", "error": None},
                {"online": False, "status_code": 302, "url": "http://portal", "error": None},
            ],
        ):
            with mock.patch("login.log_out"):
                with mock.patch("login.get_nas_id", return_value="nas-1"):
                    with mock.patch("login.get_csrf_token", return_value="csrf-token"):
                        with mock.patch("login.get_host_ip", return_value="5.6.7.8"):
                            with mock.patch.object(login.session, "post", return_value=response):
                                result = login.login_request("20240001", "secret")

        self.assertEqual(result["status"], "login_uncertain")
        self.assertEqual(result["auth_code"], "ok")

    def test_main_switches_wifi_before_login(self):
        with mock.patch("login.heading") as heading:
            with mock.patch("login.ensure_wifi_connected") as ensure_wifi_connected:
                with mock.patch(
                    "login.login_request",
                    return_value={"status": "already_online", "message": "ok"},
                ) as login_request:
                    exit_code = login.main(["login.py", "20240001", "secret"])

        self.assertEqual(exit_code, 0)
        heading.assert_called_once_with()
        ensure_wifi_connected.assert_called_once_with(login.TARGET_WIFI_SSID)
        login_request.assert_called_once_with("20240001", "secret")

    def test_main_reads_credentials_from_environment(self):
        with mock.patch.dict(
            os.environ,
            {"WHUT_USERNAME": "20240001", "WHUT_PASSWORD": "secret"},
            clear=False,
        ):
            with mock.patch("login.heading"):
                with mock.patch("login.ensure_wifi_connected"):
                    with mock.patch(
                        "login.login_request",
                        return_value={"status": "already_online", "message": "ok"},
                    ) as login_request:
                        exit_code = login.main(["login.py"])

        self.assertEqual(exit_code, 0)
        login_request.assert_called_once_with("20240001", "secret")

    def test_main_prefers_cli_credentials_over_environment(self):
        with mock.patch.dict(
            os.environ,
            {"WHUT_USERNAME": "env-user", "WHUT_PASSWORD": "env-pass"},
            clear=False,
        ):
            with mock.patch("login.heading"):
                with mock.patch("login.ensure_wifi_connected"):
                    with mock.patch(
                        "login.login_request",
                        return_value={"status": "already_online", "message": "ok"},
                    ) as login_request:
                        exit_code = login.main(["login.py", "cli-user", "cli-pass"])

        self.assertEqual(exit_code, 0)
        login_request.assert_called_once_with("cli-user", "cli-pass")

    def test_main_returns_error_when_wifi_setup_fails(self):
        with mock.patch("login.heading"):
            with mock.patch(
                "login.ensure_wifi_connected",
                side_effect=RuntimeError("nmcli missing"),
            ):
                with mock.patch("login.logging.exception") as log_exception:
                    exit_code = login.main(["login.py", "20240001", "secret"])

        self.assertEqual(exit_code, 1)
        log_exception.assert_called_once()

    def test_main_returns_usage_error_when_args_missing(self):
        with mock.patch("login.heading"):
            with mock.patch("login.logging.error") as log_error:
                exit_code = login.main(["login.py"])

        self.assertEqual(exit_code, 1)
        log_error.assert_called_once()

    def test_main_returns_2_on_login_failure(self):
        with mock.patch("login.heading"):
            with mock.patch("login.ensure_wifi_connected"):
                with mock.patch(
                    "login.login_request",
                    return_value={"status": "login_failed", "message": "密码错误"},
                ):
                    exit_code = login.main(["login.py", "20240001", "secret"])

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
