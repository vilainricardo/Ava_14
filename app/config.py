import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Pasta raiz do projeto. O .env fica nela, ao lado de requirements.txt.
BASE_DIR: Path = Path(__file__).resolve().parent.parent


def load_project_env() -> None:
    """Carrega o .env local para o ambiente do processo.

    override=False mantém um valor que já exista no ambiente. Isso
    permite que um teste ou a pipeline substituam a chave do arquivo
    sem que o .env apague essa substituição.
    """
    load_dotenv(BASE_DIR / ".env", override=False)


# A carga acontece na importação para que os módulos seguintes
# encontrem as variáveis do .env em os.environ.
load_project_env()


class Settings(BaseSettings):
    """Configurações lidas do ambiente e do .env.

    CURSOR_API_KEY fica vazia quando ninguém a definiu. O analisador
    consulta o ambiente na hora da chamada, em get_cursor_api_key.
    """

    CURSOR_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings: Settings = Settings()


def get_cursor_api_key() -> str:
    """Devolve a chave do Cursor já carregada no ambiente.

    Localmente ela vem do .env. Na pipeline ela poderá vir do secret
    do GitHub, definido no ambiente do workflow. A leitura ocorre na
    hora da chamada, então um teste consegue remover ou trocar a chave.
    """
    return os.environ.get("CURSOR_API_KEY", "").strip()
