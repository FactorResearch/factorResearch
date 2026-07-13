# Netherlands Engineering Notes

Use market code `NL` and Euronext Amsterdam symbols such as `ASML.AS`. Durable
facts belong in shared relational `market_*` tables, never JSON. The verified
CSV bundle requires: `company.csv` (`symbol,name,exchange,country,currency,regulator_id,security_type,accounting_standard`), `periods.csv` (`symbol,fiscal_year,fiscal_period,period_end,currency`), `documents.csv` (`document_id,source,url,filing_date,period_end,form,confidence`), `facts.csv` (`symbol,statement_type,fact_name,fiscal_year,fiscal_period,period_end,currency,value,source_document_id,source_url,confidence,accounting_standard,extraction_method,normalization_method`), and `shares.csv` (`symbol,shares_outstanding,as_of,source`).

`lei` or `afm_id` may replace `regulator_id`. Accepted public provenance is
AFM, Euronext Amsterdam, issuer, or licensed source. Unknown Dutch labels must
fail validation rather than being guessed. Cross-listed holding companies need
an approved ISIN/LEI/listing identity mapping before public release.
