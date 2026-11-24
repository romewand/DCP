SELECT COUNT(*) AS stored, COUNT(DISTINCT fhrs_id) AS unique_ids FROM establishments;
SELECT authority, COUNT(*) AS records, COUNT(rating_numeric) AS numeric_ratings FROM establishments GROUP BY authority;
SELECT rating_value, COUNT(*) AS records FROM establishments GROUP BY rating_value;
SELECT COUNT(*) AS flagged_dates FROM establishments WHERE date_flag_1901 = 1;
PRAGMA integrity_check;
