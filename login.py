# coding:utf-8
import logging
import os
import requests
import base64
import re
import shutil
import sys
import subprocess
import time
import socket
from urllib.parse import urlparse, parse_qs

BLUE, END = "\033[1;36m", "\033[0m"

requesr_url = ""
TARGET_WIFI_SSID = "WHUT-WLAN"
WIFI_CONNECT_RETRY_DELAY_SECONDS = 3
WIFI_CONNECT_MAX_ATTEMPTS = 3

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s: %(asctime)s ====> %(message)s"
)

session = requests.Session()
session.trust_env = False


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


def log_out():
    try:
        response = requests.get("http://172.30.21.100/api/account/logout")
        msg = response.json()
        if msg["code"] == 0:
            logging.info("try to logout, and logout succeed.")
            time.sleep(10)
    except:
        logging.info("try to logout, but logout failed.")


def get_csrf_token():
    resp = session.get("http://172.30.21.100/api/csrf-token")
    return resp.json().get("csrf_token")


def login_request(username, password) -> bool:
    if not is_net_ok():
        log_out()
        logging.info("your computer is offline，request now...")
        nasId = get_nas_id()
        logging.info("nasId: " + str(nasId))
        csrf_token = get_csrf_token()
        data = {"username": username, "password": password, "nasId": nasId}
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
        try:
            response = session.post(requesr_url, data=data, headers=headers)
            response.encoding = response.apparent_encoding

            if '"authCode":"ok' in response.text:
                logging.info("login successfully")
                user_ip = get_user_ip(response.text)
                host_ip = get_host_ip()
                logging.info("your user ip: " + user_ip)
                logging.info("your host ip: " + host_ip)
            else:
                logging.error(response.text)
        except Exception:
            logging.exception("requsest error")
    else:
        logging.info("your computer is online  ")
        host_ip = get_host_ip()
        logging.info("your host ip: " + host_ip)


def is_net_ok() -> bool:
    try:
        status = session.get("https://www.baidu.com").status_code
        if status == 200:
            return True
        else:
            return False
    except Exception:
        return False


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
    ip = match_list[0]

    return ip


def get_nas_id():
    response = session.get(
        "http://www.msftconnecttest.com/redirect", allow_redirects=True
    )
    login_url = response.url
    parsed_url = urlparse(login_url)
    query_params = parse_qs(parsed_url.query)
    nasid_list = query_params.get("nasId")
    if nasid_list:
        nasid = nasid_list[0]
        return nasid
    return -1


def heading():
    str = r"""
 _       ____  ____  ________  _       ____    ___    _   __
| |     / / / / / / / /_  __/ | |     / / /   /   |  / | / /
| | /| / / /_/ / / / / / /____| | /| / / /   / /| | /  |/ /
| |/ |/ / __  / /_/ / / /_____/ |/ |/ / /___/ ___ |/ /|  /
|__/|__/_/ /_/\____/ /_/      |__/|__/_____/_/  |_/_/ |_/
"""
    sys.stdout.write(BLUE + str + END + "\n")


def get_credentials(argv):
    if len(argv) >= 3:
        return argv[1], argv[2]

    username = os.environ.get("WHUT_USERNAME")
    password = os.environ.get("WHUT_PASSWORD")
    if username and password:
        return username, password

    return None, None


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
                login_request(username, password)
                return 0
            except Exception:
                logging.exception("Connection refused by the server..")
                logging.exception("Let me sleep for 5 seconds")
                logging.info("ZZzzzz...")
                time.sleep(5)
                logging.info("Was a nice sleep, now let me continue...")
                continue
    except Exception:
        logging.exception("startup failed")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
