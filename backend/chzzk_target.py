"""Public CHZZK channel links; no credentials or API access."""

import re
from urllib.parse import urlsplit


def parse_channel_id(value):
    if not isinstance(value, str):
        raise ValueError("치지직 방송 링크를 입력해주세요.")
    value = value.strip()
    if re.fullmatch(r"[a-fA-F0-9]{32}", value):
        return value.lower()
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or parts.hostname not in ("chzzk.naver.com", "m.chzzk.naver.com")
                or parts.username or parts.password or parts.port not in (None, 443)):
            raise ValueError()
        match = re.fullmatch(r"/(?:live/)?([a-fA-F0-9]{32})/?", parts.path)
        if match:
            return match[1].lower()
    except ValueError:
        pass
    raise ValueError("치지직 방송·채널 링크 또는 32자리 채널 ID를 입력해주세요.")
