"""Every environment switch in one place."""

import os

# The only place the model is named. Change it here or set VOUCH_MODEL, nowhere else.
MODEL_ID = os.environ.get("VOUCH_MODEL", "deepseek-chat")
API_BASE = "https://api.deepseek.com"
API_KEY_ENV = "DEEPSEEK_API_KEY"


def model_enabled() -> bool:
    return os.environ.get("MODEL", "on").strip().lower() != "off"


def check_quotes() -> bool:
    return os.environ.get("CHECK_QUOTES", "off").strip().lower() == "on"


def build_prose_checker():
    # Imported here so MODEL=off never loads the SDK, which keeps tests and offline demos
    # free of any network dependency.
    if not model_enabled():
        return None
    from vouch.model import DeepSeekProse

    return DeepSeekProse()
