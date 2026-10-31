"""Read a small, literal .env format without shell execution or interpolation."""

import os
from pathlib import Path
import re


BACKEND_ENV = Path(__file__).resolve().parent / ".env"
BACKEND_KEYS = frozenset({"OPENAI_API_KEY", "OPENAI_MODEL", "REALTIME_MODEL", "CHAT_SERVICE_TOKEN", "CHAT_SERVICE_ACCOUNTS",
                          "CHZZK_CLIENT_ID", "CHZZK_CLIENT_SECRET", "CHZZK_CHANNEL_ID", "CHZZK_REDIRECT_URI",
                          "CHZZK_SERVICE_ACCOUNT", "CHAT_PUBLIC_URL", "CHAT_HOST", "CHAT_STATE_DIR", "PORT"})
DESKTOP_KEYS = frozenset({"CHAT_SERVICE_URL", "CHAT_SERVICE_TOKEN"})


def read_env_file(path: Path, allowed_keys: frozenset[str]) -> dict[str, str]:
    """Read approved names without changing the process environment.

    Supports UTF-8/BOM, KEY=value, optional export, single/double quotes and
    comments. Values are literal: no multiline, escape or variable expansion.
    Validate the whole file before updating the process environment.
    """
    try:
        content = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError):
        raise ValueError(f"{path.name} 파일을 읽을 수 없습니다. UTF-8 형식과 파일 권한을 확인해주세요.") from None
    values = {}
    for number, raw in enumerate(content.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not match:
            raise ValueError(f"{path.name} {number}번째 줄 형식을 확인해주세요 (KEY=value).")
        key, value = match.groups()
        if key not in allowed_keys:
            continue
        if value.startswith(("'", '"')):
            closing = value.find(value[0], 1)
            tail = value[closing + 1:].strip() if closing >= 0 else ""
            if closing < 0 or (tail and not tail.startswith("#")):
                raise ValueError(f"{path.name} {number}번째 줄의 따옴표를 확인해주세요.")
            value = value[1:closing]
        else:
            value = "" if value.startswith("#") else re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if "\x00" in value:
            raise ValueError(f"{path.name} {number}번째 줄에 허용되지 않는 문자가 있습니다.")
        values[key] = value
    return values


def load_env_file(path: Path, allowed_keys: frozenset[str]) -> None:
    """Load approved names, preserving existing process environment values."""
    for key, value in read_env_file(path, allowed_keys).items():
        os.environ.setdefault(key, value)
