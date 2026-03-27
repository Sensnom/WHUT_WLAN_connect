# coding:utf-8
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

import requests

BLUE, END = "\033[1;36m", "\033[0m"

TARGET_WIFI_SSID = "WHUT-WLAN"
WIFI_CONNECT_RETRY_DELAY_SECONDS = 3
WIFI_CONNECT_MAX_ATTEMPTS = 3
LOGIN_API_URL = "http://172.30.21.100/api/authentication/login"
LOGOUT_API_URL = "http://172.30.21.100/api/account/logout"
CSRF_API_URL = "http://172.30.21.100/api/csrf-token"
REDIRECT_TEST_URL = "http://www.msftconnecttest.com/redirect"
NETWORK_TEST_URL = "https://www.baidu.com"
REQUEST_TIMEOUT_SECONDS = 15

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s: %(asctime)s ====> %(message)s"
)

session = requests.Session()
session.trust_env = False


class LoginError(RuntimeError):
    pass


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


def enable_wifi_radio():
    result = run_nmcli_command(["radio", "wifi", "on"])
    if result.returncode != 0:
        message = (
            result.stderr.strip() or result.stdout.strip() or "unknown nmcli error"
        )
        raise RuntimeError(f"failed to enable wifi: {message}")


def get_current_wifi_ssid():
    result = run_nmcli_command(["-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        if line.startswith("yes:"):
            return line.split(":", 1)[1].strip()
    return ""


def connect_wifi(target_ssid):
    result = run_nmcli_command(["dev", "wifi", "connect", target_ssid])
    if result.returncode != 0:
        message = (
            result.stderr.strip() or result.stdout.strip() or "unknown nmcli error"
        )
        raise RuntimeError(f"failed to connect to {target_ssid}: {message}")


def ensure_wifi_connected(target_ssid):
    ensure_nmcli_available()
    enable_wifi_radio()
    current_ssid = get_current_wifi_ssid()
    if current_ssid == target_ssid:
        logging.info("already connected to %s", target_ssid)
        return
    logging.info("switching wifi to %s", target_ssid)
    last_error = None
    for attempt in range(1, WIFI_CONNECT_MAX_ATTEMPTS + 1):
        try:
            connect_wifi(target_ssid)
            time.sleep(WIFI_CONNECT_RETRY_DELAY_SECONDS)
            return
        except RuntimeError as exc:
            last_error = exc
            if attempt == WIFI_CONNECT_MAX_ATTEMPTS:
                raise
            logging.warning(
                "wifi connection attempt %s/%s failed, retrying...",
                attempt,
                WIFI_CONNECT_MAX_ATTEMPTS,
            )
            time.sleep(WIFI_CONNECT_RETRY_DELAY_SECONDS)
    raise last_error


def parse_json_response(response):
    try:
        return response.json()
    except Exception:
        return None


def summarize_response_text(text, limit=300):
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def log_out():
    try:
        response = session.get(LOGOUT_API_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        payload = parse_json_response(response)
        if isinstance(payload, dict) and payload.get("code") == 0:
            logging.info("logout succeeded before re-authentication")
            time.sleep(10)
            return True
        logging.info("logout request completed but was not acknowledged: %s", payload)
        return False
    except Exception as exc:
        logging.info("logout request failed before re-authentication: %s", exc)
        return False


def get_csrf_token():
    resp = session.get(CSRF_API_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    payload = parse_json_response(resp)
    csrf_token = payload.get("csrf_token") if isinstance(payload, dict) else None
    if not csrf_token:
        raise LoginError(
            f"csrf token missing in response: {summarize_response_text(resp.text)}"
        )
    return csrf_token


def check_network_status():
    try:
        response = session.get(NETWORK_TEST_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        online = response.status_code == 200
        return {
            "online": online,
            "status_code": response.status_code,
            "url": response.url,
        }
    except Exception as exc:
        return {
            "online": False,
            "status_code": None,
            "url": NETWORK_TEST_URL,
            "error": str(exc),
        }


def is_net_ok() -> bool:
    return check_network_status()["online"]


def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def get_user_ip(response_text):
    match_list = re.findall(r'"UserIpv4":"(.*?)"', response_text, re.S)
    if len(match_list) == 0:
        return -1
    return match_list[0]


def get_nas_id():
    response = session.get(
        REDIRECT_TEST_URL,
        allow_redirects=True,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    login_url = response.url
    parsed_url = urlparse(login_url)
    query_params = parse_qs(parsed_url.query)
    nasid_list = query_params.get("nasId")
    if nasid_list:
        return nasid_list[0]
    raise LoginError(f"nasId missing in redirect url: {login_url}")


def extract_login_result(response):
    response.encoding = response.apparent_encoding
    payload = parse_json_response(response)
    text_summary = summarize_response_text(response.text)

    if isinstance(payload, dict):
        auth_code = payload.get("authCode")
        message = payload.get("message") or payload.get("msg") or text_summary
        if auth_code == "ok":
            return {
                "success": True,
                "auth_code": auth_code,
                "message": message,
                "payload": payload,
                "text_summary": text_summary,
            }
        return {
            "success": False,
            "auth_code": auth_code,
            "message": message,
            "payload": payload,
            "text_summary": text_summary,
        }

    success = '"authCode":"ok' in response.text
    return {
        "success": success,
        "auth_code": "ok" if success else None,
        "message": text_summary,
        "payload": None,
        "text_summary": text_summary,
    }


def login_request(username, password):
    network_status = check_network_status()
    if network_status["online"]:
        host_ip = get_host_ip()
        result = {
            "status": "already_online",
            "message": "network already online; login skipped",
            "host_ip": host_ip,
            "network_status": network_status,
        }
        logging.info(
            "network already online, skipping login; host_ip=%s status_code=%s",
            host_ip,
            network_status.get("status_code"),
        )
        return result

    logging.info(
        "network offline or captive before login; status=%s error=%s",
        network_status.get("status_code"),
        network_status.get("error"),
    )
    log_out()
    nas_id = get_nas_id()
    logging.info("detected nasId: %s", nas_id)
    csrf_token = get_csrf_token()
    logging.info("csrf token acquired")

    data = {"username": username, "password": password, "nasId": nas_id}
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36",
        "accept-encoding": "gzip, deflate",
        "cache-control": "max-age=0",
        "connection": "keep-alive",
        "accept-language": "zh-CN,zh-TW;q=0.8,zh;q=0.6,en;q=0.4,ja;q=0.2",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
        "x-csrf-token": csrf_token,
    }

    response = session.post(
        LOGIN_API_URL,
        data=data,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    login_result = extract_login_result(response)

    if not login_result["success"]:
        logging.error(
            "authentication rejected; auth_code=%s message=%s",
            login_result.get("auth_code"),
            login_result.get("message"),
        )
        return {
            "status": "login_failed",
            "message": login_result.get("message"),
            "auth_code": login_result.get("auth_code"),
            "nas_id": nas_id,
            "response_summary": login_result.get("text_summary"),
        }

    post_check = check_network_status()
    host_ip = get_host_ip()
    user_ip = get_user_ip(response.text)

    if post_check["online"]:
        logging.info(
            "authentication succeeded; host_ip=%s user_ip=%s status_code=%s",
            host_ip,
            user_ip,
            post_check.get("status_code"),
        )
        return {
            "status": "login_success",
            "message": login_result.get("message") or "login successfully",
            "auth_code": login_result.get("auth_code"),
            "nas_id": nas_id,
            "host_ip": host_ip,
            "user_ip": user_ip,
            "network_status": post_check,
        }

    logging.error(
        "authentication endpoint returned success but network is still offline; response=%s",
        login_result.get("text_summary"),
    )
    return {
        "status": "login_uncertain",
        "message": "authentication response looked successful but network is still offline",
        "auth_code": login_result.get("auth_code"),
        "nas_id": nas_id,
        "host_ip": host_ip,
        "user_ip": user_ip,
        "network_status": post_check,
        "response_summary": login_result.get("text_summary"),
    }


def heading():
    banner = r"""
 _       ____  ____  ________  _       ____    ___    _   __
| |     / / / / / / / /_  __/ | |     / / /   /   |  / | / /
| | /| / / /_/ / / / / / /____| | /| / / /   / /| | /  |/ /
| |/ |/ / __  / /_/ / / /_____/ |/ |/ / /___/ ___ |/ /|  /
|__/|__/_/ /_/\____/ /_/      |__/|__/_____/_/  |_/_/ |_/
"""
    sys.stdout.write(BLUE + banner + END + "\n")


def get_credentials(argv):
    if len(argv) >= 3:
        return argv[1], argv[2]

    username = os.environ.get("WHUT_USERNAME")
    password = os.environ.get("WHUT_PASSWORD")
    if username and password:
        return username, password

    return None, None


def log_login_result(result):
    logging.info("login result: %s", json.dumps(result, ensure_ascii=False, sort_keys=True))


def main(argv):
    heading()
    username, password = get_credentials(argv)
    if not username or not password:
        logging.error("usage: python3 login.py <username> <password>")
        return 1
    try:
        ensure_wifi_connected(TARGET_WIFI_SSID)
        while True:
            try:
                result = login_request(username, password)
                log_login_result(result)
                if result["status"] in {"already_online", "login_success"}:
                    return 0
                if result["status"] in {"login_failed", "login_uncertain"}:
                    return 2
                return 1
            except Exception:
                logging.exception("login flow crashed, retrying in 5 seconds")
                time.sleep(5)
                continue
    except Exception:
        logging.exception("startup failed")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
