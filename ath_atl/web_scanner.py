import threading
from pathlib import Path

from .client import BinanceClient
from .config import DEFAULT_BREAKOUTS_PATH, DEFAULT_DB_PATH, DEFAULT_SNAPSHOT_PATH, DEFAULT_STATUS_PATH
from .files import write_breakouts_json, write_json, write_snapshot_json
from .store import ATHATLStore
from .time_utils import future_iso, now_iso
from .tracker_service import ATHATLTracker
from .web_status import default_status, empty_summary, summary_warning


class BackgroundScanner:
    def __init__(
        self,
        db_path=DEFAULT_DB_PATH,
        breakouts_path=DEFAULT_BREAKOUTS_PATH,
        snapshot_path=DEFAULT_SNAPSHOT_PATH,
        status_path=DEFAULT_STATUS_PATH,
        market_types=None,
        symbols=None,
        max_symbols=None,
        request_delay=0.05,
        retry_attempts=4,
        retry_backoff=1.0,
        request_timeout=20,
        kline_limit=1000,
        scan_workers=2,
        interval_hours=24.0,
    ):
        self.db_path = Path(db_path)
        self.breakouts_path = Path(breakouts_path)
        self.snapshot_path = Path(snapshot_path)
        self.status_path = Path(status_path)
        self.market_types = market_types or ["spot", "futures"]
        self.symbols = symbols
        self.max_symbols = max_symbols
        self.request_delay = request_delay
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self.request_timeout = request_timeout
        self.kline_limit = kline_limit
        self.scan_workers = scan_workers
        self.interval_seconds = max(60, int(interval_hours * 60 * 60))
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.status = default_status(auto_scan=True)

    def start(self):
        thread = threading.Thread(target=self.run_forever, name="ath-atl-scanner", daemon=True)
        thread.start()
        return thread

    def stop(self):
        self.stop_event.set()

    def get_status(self):
        with self.lock:
            return dict(self.status)

    def set_status(self, **updates):
        with self.lock:
            self.status.update(updates)
            payload = dict(self.status)
        write_json(self.status_path, payload)

    def run_forever(self):
        self.scan_once()
        while not self.stop_event.wait(self.interval_seconds):
            self.scan_once()

    def scan_once(self):
        started_at = now_iso()
        self.set_status(
            auto_scan=True,
            running=True,
            started_at=started_at,
            error=None,
            warning=None,
            next_scan_at=None,
            summary=empty_summary(self.market_types),
            breakouts=0,
        )
        print(f"ATH/ATL scan started at {started_at}")

        store = None
        try:
            store = ATHATLStore(self.db_path)
            client = BinanceClient(
                request_delay=self.request_delay,
                retry_attempts=self.retry_attempts,
                retry_backoff=self.retry_backoff,
                timeout=self.request_timeout,
            )
            tracker = ATHATLTracker(
                client=client,
                store=store,
                kline_limit=self.kline_limit,
                scan_workers=self.scan_workers,
            )
            breakouts, summary = tracker.scan(
                market_types=self.market_types,
                symbols=self.symbols,
                max_symbols=self.max_symbols,
            )
            write_breakouts_json(self.breakouts_path, breakouts, summary)
            write_snapshot_json(self.snapshot_path, store.list_records())

            finished_at = now_iso()
            next_scan_at = future_iso(self.interval_seconds)
            warning = summary_warning(summary)
            self.set_status(
                running=False,
                finished_at=finished_at,
                next_scan_at=next_scan_at,
                error=None,
                warning=warning,
                summary=summary,
                breakouts=len(breakouts),
            )
            print(f"ATH/ATL scan finished at {finished_at}; breakouts: {len(breakouts)}")
        except Exception as exc:
            finished_at = now_iso()
            next_scan_at = future_iso(self.interval_seconds)
            self.set_status(
                running=False,
                finished_at=finished_at,
                next_scan_at=next_scan_at,
                error=str(exc),
                warning=None,
            )
            print(f"ATH/ATL scan failed at {finished_at}: {exc}")
        finally:
            if store is not None:
                store.close()
