from dataclasses import dataclass

GET_APP_LIST: str = "/IStoreService/GetAppList/v1/"
GET_PLAYER_SUMMARIES: str = "/ISteamUser/GetPlayerSummaries/v2/"
GET_SUPPORTED_API_LIST: str = "/ISteamWebAPIUtil/GetSupportedAPIList/v1/"

STEAM_STORE_API_URL: str = "https://store.steampowered.com/api"
STEAM_WEB_API_URL: str = "https://api.steampowered.com"


@dataclass(frozen=True)
class SteamRoute:
    """Rota da Steam chamada pela aplicação.

    Guarda a versão usada por esta chamada. Não informa qual versão
    a Steam considera a mais recente.
    """

    interface: str
    method: str
    version: int

    @property
    def path(self) -> str:
        return f"/{self.interface}/{self.method}/v{self.version}/"


# A v2 é a rota de notícias usada pela aplicação hoje.
GAME_NEWS_V2: SteamRoute = SteamRoute("ISteamNews", "GetNewsForApp", 2)
# A v1 existe para o teste de manutenção. Ela só declara a própria versão.
GAME_NEWS_V1: SteamRoute = SteamRoute("ISteamNews", "GetNewsForApp", 1)

GET_GAME_NEWS: str = GAME_NEWS_V2.path

# Rotas que realmente chamam a Steam e entram na verificação da pipeline.
STEAM_ROUTES: tuple[SteamRoute, ...] = (GAME_NEWS_V2, GAME_NEWS_V1)
