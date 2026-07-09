import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from codes.data import sec_data


def _response(text: str):
    response = Mock()
    response.text = text
    response.raise_for_status.return_value = None
    return response


def test_get_recent_8k_filings_fetches_primary_documents_and_strips_html():
    subs = {
        "filings": {
            "recent": {
                "form": ["10-Q", "8-K", "8-K/A"],
                "filingDate": ["2026-05-01", "2026-06-01", "2026-06-15"],
                "accessionNumber": [
                    "0001045810-26-000010",
                    "0001045810-26-000011",
                    "0001045810-26-000012",
                ],
                "primaryDocument": ["nvda-10q.htm", "nvda-8k.htm", "nvda-8ka.htm"],
            }
        }
    }

    with patch("codes.data.sec_data.get_cik", return_value=("0001045810", "NVIDIA")), \
         patch("codes.data.sec_data._fetch_submissions", return_value=subs), \
         patch("codes.data.sec_data.db.get_latest_sec_8k_accession", return_value=None), \
         patch("codes.data.sec_data.db.list_existing_sec_8k_accessions", return_value=set()), \
         patch("codes.data.sec_data.db.upsert_sec_8k_filings") as upsert_mock, \
         patch("codes.data.sec_data.db.get_sec_8k_filings", side_effect=lambda _s, limit=5: [
             {
                 "form": "8-K",
                 "filing_date": "2026-06-01",
                 "accession": "0001045810-26-000011",
                 "document": "nvda-8k.htm",
                 "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000011/nvda-8k.htm",
                 "text": "Strong growth & improvement.",
             },
             {
                 "form": "8-K/A",
                 "filing_date": "2026-06-15",
                 "accession": "0001045810-26-000012",
                 "document": "nvda-8ka.htm",
                 "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000012/nvda-8ka.htm",
                 "text": "Strong growth & improvement.",
             },
         ][:limit]), \
         patch("codes.data.sec_data.requests.get", return_value=_response(
             "<html><body><script>ignore()</script><p>Strong growth &amp; improvement.</p></body></html>"
         )) as get_mock:
        filings = sec_data.get_recent_8k_filings("nvda", limit=2)

    assert len(filings) == 2
    assert filings[0]["form"] == "8-K"
    assert filings[0]["accession"] == "0001045810-26-000011"
    assert filings[0]["source_url"].endswith(
        "/Archives/edgar/data/1045810/000104581026000011/nvda-8k.htm"
    )
    assert filings[0]["text"] == "Strong growth & improvement."
    assert "script" not in filings[0]["text"].lower()
    assert get_mock.call_count == 2
    upsert_mock.assert_called_once()
    saved = upsert_mock.call_args.args[1]
    assert len(saved) == 2
    assert saved[0]["text"] == "Strong growth & improvement."


def test_get_recent_8k_filings_uses_db_when_latest_accession_matches():
    cached_filings = [{"form": "8-K", "accession": "0001045810-26-000011", "text": "cached"}]
    subs = {
        "filings": {
            "recent": {
                "form": ["8-K"],
                "filingDate": ["2026-06-01"],
                "accessionNumber": ["0001045810-26-000011"],
                "primaryDocument": ["nvda-8k.htm"],
            }
        }
    }

    with patch("codes.data.sec_data.get_cik", return_value=("0001045810", "NVIDIA")), \
         patch("codes.data.sec_data._fetch_submissions", return_value=subs), \
         patch("codes.data.sec_data.db.get_latest_sec_8k_accession", return_value="0001045810-26-000011"), \
         patch("codes.data.sec_data.db.get_sec_8k_filings", return_value=cached_filings), \
         patch("codes.data.sec_data.db.upsert_sec_8k_filings") as upsert_mock, \
         patch("codes.data.sec_data.requests.get") as get_mock:
        filings = sec_data.get_recent_8k_filings("NVDA")

    assert filings == cached_filings
    get_mock.assert_not_called()
    upsert_mock.assert_not_called()


def test_get_recent_8k_filings_fetches_only_missing_accessions():
    subs = {
        "filings": {
            "recent": {
                "form": ["8-K", "8-K"],
                "filingDate": ["2026-06-15", "2026-06-01"],
                "accessionNumber": ["0001045810-26-000012", "0001045810-26-000011"],
                "primaryDocument": ["nvda-8ka.htm", "nvda-8k.htm"],
            }
        }
    }
    cached_filings = [
        {"form": "8-K/A", "accession": "0001045810-26-000012", "text": "new"},
        {"form": "8-K", "accession": "0001045810-26-000011", "text": "old"},
    ]

    with patch("codes.data.sec_data.get_cik", return_value=("0001045810", "NVIDIA")), \
         patch("codes.data.sec_data._fetch_submissions", return_value=subs), \
         patch("codes.data.sec_data.db.get_latest_sec_8k_accession", return_value="0001045810-26-000011"), \
         patch("codes.data.sec_data.db.list_existing_sec_8k_accessions", return_value={"0001045810-26-000011"}), \
         patch("codes.data.sec_data.db.upsert_sec_8k_filings") as upsert_mock, \
         patch("codes.data.sec_data.db.get_sec_8k_filings", return_value=cached_filings), \
         patch("codes.data.sec_data.requests.get", return_value=_response("<p>new filing</p>")) as get_mock:
        filings = sec_data.get_recent_8k_filings("NVDA", limit=2)

    assert filings == cached_filings
    assert get_mock.call_count == 1
    saved = upsert_mock.call_args.args[1]
    assert [filing["accession"] for filing in saved] == ["0001045810-26-000012"]
