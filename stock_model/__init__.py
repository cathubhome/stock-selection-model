"""Research-only A-share stock selection model."""

# AKShare 访问的交易所/东财/腾讯接口均为国内直连；requests 会读取 Windows 系统代理
# （VPN/Clash 等工具设置），经代理访问反而失败。统一禁用代理保证直连。
import os as _os

_os.environ.setdefault("NO_PROXY", "*")
_os.environ.setdefault("no_proxy", "*")
