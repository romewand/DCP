"""Prepare validated records without inventing ratings, scores, or coordinates."""
import numpy as np
import pandas as pd

from .common import write_json
from .validator import SCORES


def clean(frame, as_of, output):
    before = len(frame)
    missing_before = {k: int(v) for k, v in frame.isna().sum().items()}
    frame = frame.drop(columns="structure_ok").copy()
    exact_duplicates = int(frame.duplicated().sum())
    frame = frame.drop_duplicates()
    if frame["fhrs_id"].duplicated().any():
        raise ValueError("Conflicting IDs survived validation")
    text_changes = {}
    for column in ["business_name", "business_type", "authority", "authority_code", "postcode"]:
        old = frame[column].astype("string")
        new = old.str.replace(r"\s+", " ", regex=True).str.strip()
        if column == "postcode":
            new = new.str.upper().replace("", pd.NA)
        text_changes[column] = int((old.fillna("") != new.fillna("")).sum())
        frame[column] = new
    frame["fhrs_id"] = frame["fhrs_id"].astype("int64")
    for column in [*SCORES, "latitude", "longitude"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype("float64")
    frame["rating_numeric"] = pd.to_numeric(frame["rating_value"], errors="coerce").astype("Int64")
    parsed_dates = pd.to_datetime(frame["rating_date_raw"], utc=True, format="mixed")
    frame["date_flag_1901"] = parsed_dates.dt.strftime("%Y-%m-%d").eq("1901-01-01")
    # This is an analytical exclusion, not a claim that the FSA documented a sentinel.
    frame["inspection_date"] = parsed_dates.mask(frame["date_flag_1901"])
    age = (pd.Timestamp(as_of).normalize() - frame["inspection_date"].dt.normalize()).dt.days
    frame["days_since_rating"] = age.astype("Int64")
    # Sum across columns for each business. A missing component keeps the total missing.
    score_values = frame[["hygiene", "structural", "management"]].to_numpy(dtype=float)
    frame["score_total"] = np.sum(score_values, axis=1)
    frame["rating_band"] = np.select(
        [frame["rating_numeric"].isna(), frame["rating_numeric"].lt(3).fillna(False)],
        ["Not numerically rated", "Rating 0-2"], default="Rating 3-5")
    # Explicitly exclude special statuses and require all score components.
    focus = frame.loc[frame["rating_numeric"].lt(3).fillna(False) & frame["score_total"].notna()]
    focus.to_csv(output / "low_rated_with_scores.csv", index=False)
    frame.to_csv(output / "cleaned.csv", index=False)
    summary = {"before": before, "after": len(frame), "exact_duplicates_removed": exact_duplicates,
               "duplicate_key": "all selected source fields; conflicting FHRSIDs are quarantined at validation",
               "missing_before": missing_before,
               "missing_after": {k: int(v) for k, v in frame.isna().sum().items()},
               "text_changes": text_changes, "date_1901_flags": int(frame["date_flag_1901"].sum()),
               "numeric_ratings": int(frame["rating_numeric"].notna().sum()),
               "low_rated_with_scores": len(focus),
               "missing_value_policy": "Retain nulls; special statuses are not ratings of zero. Preserve raw date strings."}
    write_json(output / "cleaning.json", summary)
    return frame, summary
