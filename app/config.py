
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR: Path = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def get_steam_api_key() -> str:
    api_key: str | None = os.getenv("STEAM_API_KEY")

    if not api_key:
        raise ValueError("STEAM_API_KEY não configurada.")

    return api_key

def get_steam_api_url() -> str:
    api_url: str | None = os.getenv("STEAM_API_URL")

    if not api_url:
        raise ValueError("STEAM_API_URL não configurada.")

    return api_url.rstrip("/")
