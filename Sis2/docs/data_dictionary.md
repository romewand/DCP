# Data dictionary

The original complete establishment objects remain in raw JSON. SQLite contains the selected and derived fields below.

| Field | SQLite type | Meaning / missing policy |
|---|---|---|
| fhrs_id | INTEGER PRIMARY KEY | Positive unique FSA establishment identifier |
| business_name | TEXT | Whitespace-normalized business name |
| business_type | TEXT | FSA category |
| authority | TEXT | Leeds or York |
| authority_code | TEXT | FSA authority code; not the query ID |
| rating_value | TEXT | Original 0–5 rating or legitimate special status |
| rating_numeric | INTEGER nullable | Numeric rating only; statuses remain null |
| rating_date_raw | TEXT | Original source date string |
| inspection_date | TEXT nullable | ISO parsed date, excluding flagged 1901 dates |
| date_flag_1901 | INTEGER | 1 when original calendar date is 1901-01-01 |
| days_since_rating | INTEGER nullable | Days from rating to collection date; not inspection frequency |
| scheme | TEXT | FHRS |
| postcode | TEXT nullable | Trimmed uppercase postcode; blank becomes null |
| hygiene, structural | REAL nullable | Intervention scores 0,5,10,15,20,25; higher is worse |
| management | REAL nullable | Intervention score 0,5,10,20,30; higher is worse |
| latitude, longitude | REAL nullable | Coordinates; unknown values not imputed |
| score_total | REAL nullable | Sum only when all three components exist; not an independent official rating |
| rating_band | TEXT | Rating 0-2, Rating 3-5, or Not numerically rated |

Null ratings and component scores must never be replaced by zero. Exact duplicates are checked over all selected source fields. Conflicting IDs are quarantined before cleaning.
