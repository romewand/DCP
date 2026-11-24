"""Flatten source fields without cleaning, then quarantine Pandera failures."""
import copy
import numbers

import pandas as pd
import pandera.pandas as pa

from .common import write_json

RATINGS = [str(n) for n in range(6)] + ["AwaitingInspection", "AwaitingPublication", "Exempt"]
FIELDS = {"fhrs_id": "FHRSID", "business_name": "BusinessName", "business_type": "BusinessType",
          "authority": "LocalAuthorityName", "authority_code": "LocalAuthorityCode",
          "rating_value": "RatingValue", "rating_date_raw": "RatingDate", "scheme": "SchemeType",
          "postcode": "PostCode"}
SCORES = {"hygiene": "Hygiene", "structural": "Structural", "management": "ConfidenceInManagement"}


def flatten(records):
    rows = []
    for raw in records:
        source = raw if isinstance(raw, dict) else {}
        row = {}
        for column, source_key in FIELDS.items():
            row[column] = source.get(source_key)
        scores = source.get("scores")
        geocode = source.get("geocode")
        row["structure_ok"] = isinstance(raw, dict) and isinstance(scores, dict) and isinstance(geocode, dict)
        if not isinstance(scores, dict):
            scores = {}
        if not isinstance(geocode, dict):
            geocode = {}
        for column, source_key in SCORES.items():
            row[column] = scores.get(source_key)
        row["latitude"] = geocode.get("latitude")
        row["longitude"] = geocode.get("longitude")
        rows.append(row)
    return pd.DataFrame(rows, dtype=object)


def schema(as_of, authorities):
    def nonempty_text(value):
        return isinstance(value, str) and bool(value.strip())

    def positive_id(value):
        return isinstance(value, numbers.Integral) and not isinstance(value, bool) and value > 0

    def is_number(value):
        return isinstance(value, numbers.Real) and not isinstance(value, bool)

    def hygiene_score(value):
        return is_number(value) and value in [0, 5, 10, 15, 20, 25]

    def management_score(value):
        return is_number(value) and value in [0, 5, 10, 20, 30]

    def is_text(value):
        return isinstance(value, str)

    text = pa.Check(nonempty_text, element_wise=True)
    last_allowed_day = pd.Timestamp(as_of).normalize()

    def coordinate(value, limit):
        # FSA's documented JSON geocodes are numeric strings; retain them until cleaning.
        if isinstance(value, bool) or not isinstance(value, (str, numbers.Real)):
            return False
        try:
            return -limit <= float(value) <= limit
        except (TypeError, ValueError):
            return False

    def date_valid(value):
        if not isinstance(value, str):
            return False
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(parsed):
            return False
        return pd.Timestamp("1900-01-01", tz="UTC") <= parsed.normalize() <= last_allowed_day

    columns = {
        "fhrs_id": pa.Column(checks=pa.Check(positive_id, element_wise=True), unique=True),
        "business_name": pa.Column(checks=text), "business_type": pa.Column(checks=text),
        "authority": pa.Column(checks=pa.Check.isin(authorities)),
        "authority_code": pa.Column(checks=text),
        "rating_value": pa.Column(checks=pa.Check.isin(RATINGS)),
        "rating_date_raw": pa.Column(checks=pa.Check(date_valid, element_wise=True, name="parseable_nonfuture_date")),
        "scheme": pa.Column(checks=pa.Check.eq("FHRS")),
        "postcode": pa.Column(checks=pa.Check(is_text, element_wise=True), nullable=True),
        "structure_ok": pa.Column(checks=pa.Check.eq(True)),
    }
    columns["hygiene"] = pa.Column(nullable=True, checks=pa.Check(hygiene_score, element_wise=True))
    columns["structural"] = pa.Column(nullable=True, checks=pa.Check(hygiene_score, element_wise=True))
    columns["management"] = pa.Column(nullable=True, checks=pa.Check(management_score, element_wise=True))

    def latitude_valid(value):
        return coordinate(value, 90)

    def longitude_valid(value):
        return coordinate(value, 180)

    columns["latitude"] = pa.Column(nullable=True, checks=pa.Check(latitude_valid, element_wise=True))
    columns["longitude"] = pa.Column(nullable=True, checks=pa.Check(longitude_valid, element_wise=True))
    return pa.DataFrameSchema(columns, strict=True, coerce=False)


def validate(records, as_of, authorities, output):
    output.mkdir(parents=True, exist_ok=True)
    if not records:
        raise ValueError("No records to validate")
    frame = flatten(records)
    failures = pd.DataFrame(columns=["schema_context", "column", "check", "failure_case", "index"])
    try:
        schema(as_of, authorities).validate(frame, lazy=True)
    except pa.errors.SchemaErrors as error:
        failures = error.failure_cases
        if failures["index"].isna().any():
            failures.to_csv(output / "schema_errors.csv", index=False)
            raise RuntimeError("Dataset-level schema failure; refusing to guess affected rows") from error
    invalid_indices = sorted(set(failures["index"].astype(int)))
    valid = frame.drop(index=invalid_indices).copy()
    failures.to_csv(output / "validation_errors.csv", index=False)
    write_json(output / "quarantine.json", [{"source_index": i, "record": records[i]} for i in invalid_indices])
    summary = {"received": len(frame), "valid": len(valid), "invalid": len(invalid_indices),
               "rules": "positive unique ID; required text; selected authority; FHRS scheme; rating category; date; score domains; coordinates; JSON structure"}
    write_json(output / "validation.json", summary)
    return valid, summary


def demonstrate_invalid_records(record, as_of, authorities, output):
    cases = [copy.deepcopy(record) for _ in range(4)]
    for i, row in enumerate(cases):
        row["FHRSID"] = 900000001 + i
    cases[0]["RatingValue"] = "99"
    cases[1]["BusinessName"] = "   "
    cases[2]["RatingDate"] = "2099-01-01T00:00:00"
    cases[3]["scores"]["Hygiene"] = -5
    valid, summary = validate(cases, as_of, authorities, output)
    write_json(output / "test_records.json", {"synthetic": True, "excluded_from_final_data": True, "records": cases})
    if len(valid) != 0 or summary["invalid"] != 4:
        raise AssertionError("The schema did not reject all four deliberately invalid records")
    return summary
