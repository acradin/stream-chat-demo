"""Load the operator's root-managed runtime file before starting the backend."""

import argparse
import json
import os
from pathlib import Path
import sys

from backend.env import BACKEND_KEYS
from backend.chzzk import ChzzkConfig, credential
from backend.chzzk_remote import public_origin
from backend.server import validate_accounts
from backend.screenshot_provider import OpenAIScreenshotProvider


def validate_config(config):
    if (not isinstance(config, dict) or set(config) - BACKEND_KEYS
            or any(not isinstance(value, str) or any(c in value for c in "\r\n\x00") for value in config.values())):
        raise ValueError("Invalid server configuration")
    accounts = (json.loads(config["CHAT_SERVICE_ACCOUNTS"]) if config.get("CHAT_SERVICE_ACCOUNTS") else
                {"development": config.get("CHAT_SERVICE_TOKEN", "")})
    validate_accounts(accounts)
    if config.get("CHZZK_SERVICE_ACCOUNT", "development") not in accounts:
        raise ValueError("CHZZK service account must match a configured service account")
    origin = public_origin(config.get("CHAT_PUBLIC_URL", ""))
    if config.get("CHZZK_REDIRECT_URI") != origin + "/oauth/chzzk/callback":
        raise ValueError("CHZZK callback must use the public server origin")
    ChzzkConfig(config.get("CHZZK_CLIENT_ID", ""), config.get("CHZZK_CLIENT_SECRET", ""),
                config.get("CHZZK_CHANNEL_ID", ""), config["CHZZK_REDIRECT_URI"])
    api_key = credential(config.get("OPENAI_API_KEY", ""), "OPENAI_API_KEY")
    OpenAIScreenshotProvider(model=config.get("OPENAI_MODEL", "gpt-6-astra"), api_key=api_key)
    if (config.get("CHAT_HOST") != "127.0.0.1" or config.get("PORT") != "8766"
            or config.get("CHAT_STATE_DIR") != "/var/lib/stream-chat"):
        raise ValueError("Backend must bind to loopback and use its persistent state directory")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("/etc/stream-chat/runtime.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        config = validate_config(json.loads(args.config.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        parser.exit(1, "Server configuration is invalid; check the operator settings.\n")
    if args.check:
        print("Server configuration valid; no AI or CHZZK requests sent.")
        return
    for key in BACKEND_KEYS:
        os.environ.pop(key, None)
    os.environ.update(config)
    sys.argv = ["backend.server"]
    from backend.server import main as serve
    serve()


if __name__ == "__main__":
    main()
