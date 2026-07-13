"""Factor return datasets for V2.2 factor research."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from urllib.request import urlopen

import pandas as pd

from codes.data import db

KEN_FRENCH_FF5_MONTHLY_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_CSV.zip"
)
KEN_FRENCH_MOM_MONTHLY_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Momentum_Factor_CSV.zip"
)

_SOURCE = "ken_french_us"
_PERIOD = "monthly"


def get_us_monthly_factors(*, force_refresh: bool = False) -> pd.DataFrame:
    """Return monthly U.S. factor returns as decimals."""
    if not force_refresh:
        stored = db.get_factor_returns(source=_SOURCE, period=_PERIOD)
        if stored:
            return _records_to_frame(stored)

    ff5 = _download_ken_french_zip(KEN_FRENCH_FF5_MONTHLY_URL)
    mom = _download_ken_french_zip(KEN_FRENCH_MOM_MONTHLY_URL)
    factors = _merge_factor_frames(ff5, mom)
    db.upsert_factor_returns(
        factors.to_dict("records"),
        source=_SOURCE,
        period=_PERIOD,
    )
    return factors


def _download_ken_french_zip(url: str) -> pd.DataFrame:
    with urlopen(url, timeout=20) as response:
        payload = response.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("Ken French zip did not contain a CSV file")
        text = archive.read(csv_names[0]).decode("utf-8-sig", errors="replace")
    return _parse_ken_french_csv(text)


def _parse_ken_french_csv(text: str) -> pd.DataFrame:
    rows = []
    reader = csv.reader(io.StringIO(text))
    headers = None
    for raw in reader:
        cells = [cell.strip() for cell in raw]
        if not cells:
            continue
        if (
            cells[0].lower() in {"date", "yyyymm"}
            or cells[0].startswith("Unnamed")
            or (not cells[0] and any(_normalize_headers(cells[1:])))
        ):
            headers = _normalize_headers(cells)
            continue
        if not cells[0]:
            continue
        if not cells[0].isdigit() or len(cells[0]) != 6:
            if rows:
                break
            continue
        if headers is None:
            continue
        row = {"Date": _month_end(cells[0])}
        for header, value in zip(headers[1:], cells[1:]):
            if not header:
                continue
            row[header] = float(value) / 100.0
        rows.append(row)
    if not rows:
        raise ValueError("No monthly factor rows parsed")
    return pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)


def _normalize_headers(headers: list[str]) -> list[str]:
    mapping = {
        "mkt-rf": "mkt_rf",
        "mktrf": "mkt_rf",
        "smb": "smb",
        "hml": "hml",
        "rmw": "rmw",
        "cma": "cma",
        "rf": "rf",
        "mom": "mom",
    }
    normalized = []
    for header in headers:
        key = header.lower().replace(" ", "").replace("_", "-")
        normalized.append(mapping.get(key, key.replace("-", "_")))
    return normalized


def _month_end(yyyymm: str) -> str:
    year = int(yyyymm[:4])
    month = int(yyyymm[4:])
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (pd.Timestamp(next_month) - pd.Timedelta(days=1)).date().isoformat()


def _merge_factor_frames(ff5: pd.DataFrame, mom: pd.DataFrame) -> pd.DataFrame:
    merged = ff5.merge(mom[["Date", "mom"]], on="Date", how="left")
    columns = ["Date", "mkt_rf", "smb", "hml", "rmw", "cma", "mom", "rf"]
    return merged[[column for column in columns if column in merged.columns]].dropna(subset=["mkt_rf", "smb", "hml"])


def _records_to_frame(records: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if not frame.empty and "Date" in frame:
        frame["Date"] = pd.to_datetime(frame["Date"]).dt.strftime("%Y-%m-%d")
    return frame
