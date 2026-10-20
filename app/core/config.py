import ipaddress
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "fastapi"
    debug: bool = False
    log_dir: str = "logs"
    # lowest level written to the daily log file; empty = no file logging
    log_file_level: Literal["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = ""
    log_file_retention_days: int = 14  # 0 = keep forever
    database_url: str
    redis_url: str
    celery_broker_url: str = "redis://localhost:6379/1"  # own Redis DB, apart from the limiter
    rate_limit: str = "60/minute"
    secret_key: str
    access_token_expire_minutes: int = 30
    # comma-separated IPs/CIDRs allowed to supply X-Request-ID; empty = trust nobody
    trusted_proxies: str = ""
    # Google Chat add-on webhook; empty = endpoint rejects everything
    google_chat_audience: str = ""  # exact HTTP endpoint URL set in the Chat API console
    google_chat_service_account_email: str = ""  # service-<project-number>@gcp-sa-gsuiteaddons...
    # web page crawler
    crawler_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    )
    crawler_timeout_seconds: float = 15
    crawler_max_bytes: int = 5 * 1024 * 1024  # cap on the decompressed response body
    # dev-only defaults for `cli seed-user`
    seed_user_name: str = "Admin"
    seed_user_email: str = "admin@example.com"
    seed_user_password: str = "password123"

    @property
    def trusted_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [
            ipaddress.ip_network(p.strip(), strict=False)
            for p in self.trusted_proxies.split(",")
            if p.strip()
        ]


settings = Settings()
