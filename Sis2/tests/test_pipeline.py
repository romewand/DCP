"""Small edge-case tests for validation, missing data, and exact SQLite idempotency."""
import copy
import tempfile
import unittest
from pathlib import Path

from src.cleaner import clean
from src.loader import load_twice
from src.validator import validate

AS_OF = "2026-11-16T12:00:00+00:00"
RECORD = {"FHRSID": 1, "BusinessName": " Test  cafe ", "BusinessType": "Restaurant/Cafe/Canteen",
          "LocalAuthorityName": "Leeds", "LocalAuthorityCode": "413", "RatingValue": "0",
          "RatingDate": "2026-11-05T00:00:00", "SchemeType": "FHRS", "PostCode": " ls1 1aa ",
          "scores": {"Hygiene": 25, "Structural": 20, "ConfidenceInManagement": 30},
          "geocode": {"latitude": "53.8", "longitude": "-1.5"}}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, rows):
        return validate(rows, AS_OF, ["Leeds", "York"], self.path)

    def test_zero_rating_and_numeric_coordinate_strings_are_valid(self):
        frame, result = self.validate([RECORD])
        self.assertEqual(result["invalid"], 0)
        cleaned, _ = clean(frame, AS_OF, self.path)
        self.assertEqual(cleaned.iloc[0].rating_numeric, 0)
        self.assertEqual(cleaned.iloc[0].business_name, "Test cafe")
        self.assertEqual(cleaned.iloc[0].days_since_rating, 11)

    def test_special_status_and_1901_date_remain_a_record(self):
        row = copy.deepcopy(RECORD)
        row.update(RatingValue="AwaitingInspection", RatingDate="1901-01-01T00:00:00")
        row["scores"] = dict.fromkeys(row["scores"])
        row["geocode"] = {"latitude": None, "longitude": None}
        frame, result = self.validate([row])
        self.assertEqual(result["invalid"], 0)
        cleaned, _ = clean(frame, AS_OF, self.path)
        self.assertTrue(cleaned.iloc[0].date_flag_1901)
        self.assertTrue(cleaned[["inspection_date", "rating_numeric", "score_total"]].isna().all().all())
        self.assertEqual(cleaned.iloc[0].rating_date_raw, row["RatingDate"])

    def test_invalid_fields_quarantine_only_the_affected_record(self):
        for field, value in [("FHRSID", False), ("BusinessName", " "), ("RatingValue", "8"),
                             ("RatingDate", "not-a-date"), ("RatingDate", "2099-01-01"),
                             ("SchemeType", "FHIS"), ("LocalAuthorityName", "Elsewhere")]:
            with self.subTest(field=field, value=value):
                bad = copy.deepcopy(RECORD)
                bad["FHRSID"] = 2
                bad[field] = value
                _, result = self.validate([RECORD, bad])
                self.assertEqual((result["valid"], result["invalid"]), (1, 1))

    def test_duplicate_ids_quarantine_both_ambiguous_rows(self):
        _, result = self.validate([RECORD, copy.deepcopy(RECORD)])
        self.assertEqual(result["invalid"], 2)

    def test_invalid_coordinates_and_scores(self):
        for area, key, value in [("geocode", "latitude", "91"), ("geocode", "longitude", "nan"),
                                  ("scores", "Hygiene", -1), ("scores", "ConfidenceInManagement", 15)]:
            with self.subTest(area=area, key=key, value=value):
                bad = copy.deepcopy(RECORD)
                bad[area][key] = value
                _, result = self.validate([bad])
                self.assertEqual(result["invalid"], 1)

    def test_partial_scores_do_not_become_a_complete_total(self):
        row = copy.deepcopy(RECORD)
        row["scores"]["Hygiene"] = None
        frame, _ = self.validate([row])
        cleaned, _ = clean(frame, AS_OF, self.path)
        self.assertTrue(cleaned["score_total"].isna().all())

    def test_empty_input_fails_with_clear_message(self):
        with self.assertRaisesRegex(ValueError, "No records"):
            self.validate([])

    def test_mixed_valid_date_formats_are_cleaned(self):
        second = copy.deepcopy(RECORD)
        second.update(FHRSID=2, RatingDate="2026-11-05")
        frame, result = self.validate([RECORD, second])
        self.assertEqual(result["valid"], 2)
        cleaned, _ = clean(frame, AS_OF, self.path)
        self.assertEqual(cleaned["days_since_rating"].tolist(), [11, 11])

    def test_processing_skips_invalid_first_record_for_demo(self):
        from unittest.mock import patch
        from src.common import write_json, digest
        from main import process
        bad = copy.deepcopy(RECORD)
        bad["scores"] = None
        good = copy.deepcopy(RECORD)
        good["FHRSID"] = 2
        records = [bad, good]
        write_json(self.path / "run.json", {"source_hashes": {}, "records_sha256": digest(records),
                   "as_of": AS_OF, "authorities": ["Leeds", "York"], "run_id": "test", "expected": 2})
        write_json(self.path / "consumed.json", records)
        write_json(self.path / "consumer.json", {"complete": True, "consumed": 2})
        write_json(self.path / "producer.json", {"published": 2})
        with patch("main.ROOT", self.path), patch("src.analysis.analyse"):
            result = process(self.path)
        self.assertEqual(result["counts"]["invalid"], 1)
        self.assertEqual(result["counts"]["stored"], 1)
        self.assertEqual(result["synthetic_invalid_records_excluded"], 4)

    def test_sqlite_reload_matches_every_value(self):
        frame, _ = self.validate([RECORD])
        cleaned, _ = clean(frame, AS_OF, self.path)
        result = load_twice(cleaned, self.path)
        self.assertEqual(result["second_load_changes"], 0)
        self.assertEqual(result["first_content_sha256"], result["second_content_sha256"])
        changed = cleaned.copy()
        changed.loc[0, "business_name"] = "Changed source"
        with self.assertRaises(AssertionError):
            load_twice(changed, self.path)


if __name__ == "__main__":
    unittest.main()
