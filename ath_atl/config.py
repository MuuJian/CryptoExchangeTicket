from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
DAY_MS = 24 * 60 * 60 * 1000
DEFAULT_DB_PATH = DATA_DIR / "ath_atl.db"
DEFAULT_BREAKOUTS_PATH = DATA_DIR / "daily_breakouts.json"
DEFAULT_SNAPSHOT_PATH = DATA_DIR / "ath_atl_snapshot.json"
DEFAULT_STATUS_PATH = DATA_DIR / "scan_status.json"
ATH_ATL_COLUMNS = [
    "market_type",
    "symbol",
    "current_price",
    "ath_price",
    "atl_price",
    "first_kline_open_time",
    "last_kline_open_time",
    "updated_at",
]
