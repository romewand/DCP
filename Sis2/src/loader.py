"""Store a run snapshot and prove repeat loading changes neither rows nor values."""
import pandas as pd
import sqlite3
from contextlib import closing

from .common import ROOT, digest, write_json

COLUMNS = ["fhrs_id", "business_name", "business_type", "authority", "authority_code", "rating_value",
           "rating_date_raw", "scheme", "postcode", "hygiene", "structural", "management", "latitude",
           "longitude", "rating_numeric", "date_flag_1901", "inspection_date", "days_since_rating",
           "score_total", "rating_band"]


def load_twice(frame, output):
    database = output / "output.db"
    values = frame[COLUMNS].copy()
    values["date_flag_1901"] = values["date_flag_1901"].astype(int)
    values["inspection_date"] = values["inspection_date"].dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    # Convert pandas missing values to Python None, which SQLite stores as NULL.
    values = values.astype(object).where(values.notna(), None)
    rows = list(values.itertuples(index=False, name=None))
    placeholders = ",".join("?" for _ in COLUMNS)
    sql = f"INSERT INTO establishments ({','.join(COLUMNS)}) VALUES ({placeholders}) ON CONFLICT(fhrs_id) DO NOTHING"
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript((ROOT / "sql/schema.sql").read_text(encoding="utf-8"))
        connection.executemany(sql, rows)
        connection.commit()
        first = connection.execute(f"SELECT {','.join(COLUMNS)} FROM establishments ORDER BY fhrs_id").fetchall()
        first_changes = connection.total_changes
        connection.executemany(sql, rows)
        connection.commit()
        second = connection.execute(f"SELECT {','.join(COLUMNS)} FROM establishments ORDER BY fhrs_id").fetchall()
        repeat_changes = connection.total_changes - first_changes
        expected = sorted(rows, key=lambda row: row[0])
        if first != expected or second != expected or repeat_changes != 0:
            raise AssertionError("SQLite content, count, or idempotency mismatch")
        verification = {}
        for statement in (ROOT / "sql/verify.sql").read_text(encoding="utf-8").split(";"):
            if statement.strip():
                cursor = connection.execute(statement)
                verification[statement.strip()] = [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
    result = {"stored": len(second), "first_load_count": len(first), "second_load_count": len(second),
              "second_load_changes": repeat_changes, "first_content_sha256": digest(first),
              "second_content_sha256": digest(second), "matches_processed_values": True,
              "sql_results": verification}
    write_json(output / "database_verification.json", result)
    return result
