# France Engineering Notes

France uses market code `FR`, Euronext Paris symbols such as `AI.PA`, and the
shared relational market schema. Do not add a country database or durable JSON
payloads.

The verified-import bundle is five UTF-8 CSV files:

- `company.csv`: `symbol,name,exchange,country,currency,regulator_id,security_type,accounting_standard`
- `periods.csv`: `symbol,fiscal_year,fiscal_period,period_end,currency`
- `documents.csv`: `document_id,source,url,filing_date,period_end,form,confidence`
- `facts.csv`: `symbol,statement_type,fact_name,fiscal_year,fiscal_period,period_end,currency,value,source_document_id,source_url,confidence,accounting_standard,extraction_method,normalization_method`
- `shares.csv`: `symbol,shares_outstanding,as_of,source`

`lei` or `amf_id` may replace `regulator_id`. Accepted public provenance is
AMF, Euronext Paris, issuer, or licensed source. French labels are mapped only
when explicitly listed in `france_normalization.py`; an unknown label fails the
quality gate rather than being guessed.
