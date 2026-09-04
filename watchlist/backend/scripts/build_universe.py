import csv
import io
import json
from pathlib import Path

import httpx

SOURCES = [
    "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
    "https://archives.nseindia.com/content/indices/ind_niftymidcap50list.csv",
]
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept": "text/csv,*/*;q=0.8",
}
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "data" / "universe.json"


def fetch_rows(url: str) -> list[dict[str, str]]:
    response = httpx.get(url, headers=BROWSER_HEADERS, timeout=30, follow_redirects=True)
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text))
    return [{k.strip(): v.strip() for k, v in row.items()} for row in reader]


def to_entry(row: dict[str, str]) -> dict[str, str]:
    return {
        "symbol": f"{row['Symbol']}.NS",
        "name": row["Company Name"],
        "industry": row["Industry"],
        "isin": row["ISIN Code"],
    }


def main() -> None:
    entries = [to_entry(row) for url in SOURCES for row in fetch_rows(url)]
    entries.sort(key=lambda e: e["symbol"])
    symbols = {e["symbol"] for e in entries}
    assert len(entries) == 150, f"expected 150 constituents, got {len(entries)}"
    assert len(symbols) == 150, "duplicate symbols across the two lists"
    assert "TMPV.NS" in symbols, "TMPV.NS missing"
    assert "TATAMOTORS.NS" not in symbols, "TATAMOTORS.NS should be gone"
    OUTPUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(entries)} symbols to {OUTPUT}")


if __name__ == "__main__":
    main()
