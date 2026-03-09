from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field

BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
ENV_FILES = tuple(str(p) for p in (ROOT_ENV_FILE, BACKEND_ENV_FILE) if p.exists())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    # App
    app_name: str = "FundWatch"
    debug: bool = False

    # Database
    database_url: str

    # Auth
    secret_key: str
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Stripe
    stripe_secret_key: str
    stripe_webhook_secret: str = "whsec_todo"
    stripe_price_pro_monthly: str = "price_todo"
    stripe_price_team_monthly: str = "price_todo"

    # Email (Resend)
    resend_api_key: str = ""
    email_from: str = "FundWatch <alerts@sustainovate.com>"

    # Playwright
    playwright_headless: bool = True
    crawler_max_calls_per_source: int = 50
    crawler_max_pages: int = 5
    crawler_max_listing_links: int = 3

    # Matcher / LLM (always LLM-only scoring)
    matcher_llm_provider: str = "anthropic"  # "anthropic" | "openai"
    matcher_openai_model: str = "gpt-4o-mini"
    matcher_anthropic_model: str = "claude-sonnet-4-6"
    matcher_min_score: int = 60
    openai_api_key: str = ""
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    )

settings = Settings()
