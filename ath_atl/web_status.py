def default_status(auto_scan):
    return {
        "auto_scan": auto_scan,
        "running": False,
        "started_at": None,
        "finished_at": None,
        "next_scan_at": None,
        "error": None,
        "warning": None,
        "summary": {},
        "breakouts": 0,
    }


def summary_warning(summary):
    error_count = sum(item.get("errors", 0) for item in summary.values())
    if not error_count:
        return None
    return f"{error_count} symbols failed; scan continued"


def empty_summary(market_types):
    return {
        market_type: {
            "symbols": 0,
            "processed": 0,
            "breakouts": 0,
            "errors": 0,
            "failed_symbols": [],
        }
        for market_type in market_types
    }
