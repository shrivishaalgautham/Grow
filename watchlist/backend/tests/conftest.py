import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://watchlist:watchlist@localhost:5432/watchlist"
os.environ["REDIS_URL"] = ""
os.environ["REPLAY_DATE"] = ""
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173"
