from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    kalshi_env: str = Field(default='demo', alias='KALSHI_ENV')
    kalshi_api_key_id: str | None = Field(default=None, alias='KALSHI_API_KEY_ID')
    kalshi_private_key_path: str | None = Field(default=None, alias='KALSHI_PRIVATE_KEY_PATH')
    database_url: str = Field(default='sqlite:///./kalshi_dashboard.db', alias='DATABASE_URL')
    snapshot_limit: int = Field(default=200, alias='SNAPSHOT_LIMIT')
    snapshot_interval_minutes: int = Field(default=5, alias='SNAPSHOT_INTERVAL_MINUTES')
    public_market_limit: int = Field(default=10_000, alias='PUBLIC_MARKET_LIMIT')
    app_auth_required: bool = Field(default=False, alias='APP_AUTH_REQUIRED')
    app_username: str = Field(default='admin', alias='APP_USERNAME')
    app_password: str | None = Field(default=None, alias='APP_PASSWORD')

    @property
    def base_url(self) -> str:
        if self.kalshi_env.lower() == 'prod':
            return 'https://api.elections.kalshi.com/trade-api/v2'
        return 'https://demo-api.kalshi.co/trade-api/v2'

    @property
    def public_market_base_url(self) -> str:
        """Public production market data never needs private credentials."""
        return 'https://api.elections.kalshi.com/trade-api/v2'

    @property
    def public_websocket_url(self) -> str:
        """Read-only public ticker stream; no account credentials are sent."""
        return 'wss://api.elections.kalshi.com/trade-api/ws/v2'

    @property
    def has_api_credentials(self) -> bool:
        """Public market data works without credentials; private endpoints do not."""
        return bool(self.kalshi_api_key_id and self.kalshi_private_key_path)

    @property
    def login_enabled(self) -> bool:
        """Enable the app login when a password is configured or explicitly required."""
        return self.app_auth_required or bool(self.app_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()
