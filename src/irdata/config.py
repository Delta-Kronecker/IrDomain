import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOGS_DIR = ROOT / "logs"
DB_PATH = DATA_DIR / "irdata.sqlite"

for _d in (RAW_DIR, PROCESSED_DIR, LOGS_DIR, DATA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

USER_AGENT = "IrDomainBot/0.1 (research; github.com/Delta-Kronecker/IrDomain)"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

HTTP_TIMEOUT = 30.0
HTTP_RETRIES = 3
RADAR_API_TOKEN = os.environ.get("RADAR_API_TOKEN", "")

FETCH_CONCURRENCY = 50
FETCH_TIMEOUT = 15.0
FETCH_MAX_BYTES = 500_000

IR_SECOND_LEVEL = {
    "ac", "co", "com", "edu", "gov", "id", "net", "news",
    "org", "priv", "sch", "web",
}
