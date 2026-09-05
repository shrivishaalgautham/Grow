import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://watchlist:watchlist@localhost:5433/watchlist"
os.environ["REDIS_URL"] = ""
os.environ["REPLAY_DATE"] = ""
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173"

from app.config import settings  # noqa: E402

settings.redis_url = ""
settings.yahoo_impersonate = ""
settings.openrouter_api_key = ""
settings.google_api_key = ""
settings.email_transport = "console"
