# WHUT_WLAN

武汉理工大学校园网自动登陆脚本

```txt
 _       ____  ____  ________  _       ____    ___    _   __
| |     / / / / / / / /_  __/ | |     / / /   /   |  / | / /
| | /| / / /_/ / / / / / /____| | /| / / /   / /| | /  |/ /
| |/ |/ / __  / /_/ / / /_____/ |/ |/ / /___/ ___ |/ /|  /
|__/|__/_/ /_/\____/ /_/      |__/|__/_____/_/  |_/_/ |_/
```

## 使用方法

先使用 `uv` 创建项目环境并安装依赖：

```shell
uv sync
```

Linux 环境还需要 `nmcli`，也就是系统启用了 NetworkManager。

脚本现在会在每次运行时先自动打开 Wi-Fi，再尝试把当前网络切换到 `WHUT-WLAN`，切换成功后再执行校园网认证登录。

脚本也支持从环境变量读取账号密码：`WHUT_USERNAME` 和 `WHUT_PASSWORD`。

如果没有传入账号和密码，脚本会输出用法提示并退出，而不会直接报 `IndexError`。

手动登录：

```shell
.venv/bin/python login.py yourNumber yourPassword
```

## 开机自启（oneshot + timer）

先执行：

```shell
uv sync
```

然后运行下面的安装脚本。它会自动探测当前项目目录、当前用户家目录，并使用项目内 `.venv/bin/python` 生成用户级 `systemd` 的 **oneshot service + timer**：

```shell
python3 install_autostart.py
```

也可以直接传参，避免交互输入：

```shell
python3 install_autostart.py --username yourNumber --password yourPassword
```

安装脚本会：

- 在项目目录生成 `whut-wlan.env`
- 在 `~/.config/systemd/user/` 生成 `whut-wlan.service`
- 在 `~/.config/systemd/user/` 生成 `whut-wlan.timer`
- 使用项目内 `.venv/bin/python` 作为执行解释器
- 自动执行 `systemctl --user daemon-reload`
- 自动关闭旧的 `whut-wlan.service` 常驻模式
- 自动执行 `systemctl --user enable --now whut-wlan.timer`
- 安装完成后立刻手动触发一次 `whut-wlan.service`

当前默认调度策略：

- 开机后 `30s` 触发一次
- 之后每 `10min` 再触发一次

注意：`whut-wlan.env` 中保存的是明文账号密码，请不要提交、分享或同步这个文件。安装脚本会将它的权限设置为仅当前用户可读写。

这个服务是用户级 `systemd` 服务。通常会在用户登录后自动启动；如果你希望无人登录也能在开机后运行，需要额外执行：

```shell
loginctl enable-linger "$USER"
```

查看 timer 状态：

```shell
systemctl --user status whut-wlan.timer
systemctl --user list-timers --all | grep whut-wlan
```

手动立即执行一次登录检查：

```shell
systemctl --user start whut-wlan.service
```

一键删除自动启动：

```shell
python3 install_autostart.py --uninstall
```

它会停止并移除 `whut-wlan.service` 和 `whut-wlan.timer`，但默认保留 `whut-wlan.env`，方便后续重新安装。
