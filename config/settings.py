import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PROFILE_DIR = Path(os.environ.get("LINKEDIN_PROFILE_DIR", Path.home() / ".linkedin_agent_profile"))

DATABASE_PATH = BASE_DIR / "data" / "jobs.db"

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

DEFAULT_MODEL = "llama3.2"

MATCH_SCORE_THRESHOLD = int(os.environ.get("MATCH_SCORE_THRESHOLD", "6"))

SCRAPE_LIMIT_PER_BUCKET = int(os.environ.get("SCRAPE_LIMIT_PER_BUCKET", "50"))

SCROLL_PAUSE_SEC = 2.0

MAX_SCROLLS = 30

TIME_BUCKETS = [
    ("<30m", 30),
    ("<1h", 60),
    ("<3h", 180),
    ("<6h", 360),
    ("<24h", 1440),
]

LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs/search/"

CSV_EXPORT_DIR = BASE_DIR / "data"

for d in [PROFILE_DIR, DATABASE_PATH.parent, CSV_EXPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)
