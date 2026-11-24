"""Run collection -> Kafka -> Pandera -> cleaning -> SQLite -> EDA."""
import argparse
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.api_client import collect
from src.common import ROOT, digest, file_hash, now, read_json, write_json


def prepare(raw_directory, bootstrap):
    raw_directory = Path(raw_directory).resolve()
    manifest = read_json(raw_directory / "collection_manifest.json")
    records = read_json(raw_directory / "records.json")
    if not manifest["complete"] or len(records) < 200 or len(records) != manifest["count"] or digest(records) != manifest["records_sha256"]:
        raise ValueError("Collection manifest or data verification failed")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = ROOT / "data/runs" / run_id
    run_dir.mkdir(parents=True)
    config = {"run_id": run_id, "topic": "sis2-" + run_id.lower(), "bootstrap": bootstrap,
              "raw_directory": raw_directory.relative_to(ROOT).as_posix(), "expected": len(records),
              "records_sha256": manifest["records_sha256"], "as_of": manifest["finished_at_utc"],
              "authorities": [item["authority"] for item in manifest["coverage"]],
              "source_hashes": {p.relative_to(ROOT).as_posix(): file_hash(p)
                                for p in [ROOT / "main.py", *sorted((ROOT / "src").glob("*.py")),
                                          *sorted((ROOT / "sql").glob("*.sql")), ROOT / "compose.yaml"]}}
    write_json(run_dir / "run.json", config)
    return run_dir


def process(run_dir):
    from src.validator import validate, demonstrate_invalid_records
    from src.cleaner import clean
    from src.loader import load_twice
    from src.analysis import analyse

    config = read_json(run_dir / "run.json")
    for filename, expected_hash in config["source_hashes"].items():
        if file_hash(ROOT / filename) != expected_hash:
            raise ValueError(f"Source changed since run preparation: {filename}; prepare a new run")
    records = read_json(run_dir / "consumed.json")
    consumer = read_json(run_dir / "consumer.json")
    producer = read_json(run_dir / "producer.json")
    if not consumer["complete"] or digest(records) != config["records_sha256"]:
        raise ValueError("Cannot process incomplete or modified Kafka output")
    frame, validation = validate(records, config["as_of"], config["authorities"], run_dir)
    if frame.empty:
        raise ValueError("All records failed validation; inspect quarantine.json before continuing")
    # Build synthetic cases from a record that passed validation.
    demonstration = demonstrate_invalid_records(records[int(frame.index[0])], config["as_of"], config["authorities"], run_dir / "invalid_demo")
    cleaned, cleaning = clean(frame, config["as_of"], run_dir)
    database = load_twice(cleaned, run_dir)
    analyse(run_dir)
    counts = {"api": config["expected"], "published": producer["published"], "consumed": consumer["consumed"],
              "valid": validation["valid"], "invalid": validation["invalid"], "cleaned": len(cleaned), "stored": database["stored"]}
    checks = {"api_equals_published_equals_consumed": counts["api"] == counts["published"] == counts["consumed"],
              "validation_reconciles": counts["consumed"] == counts["valid"] + counts["invalid"],
              "cleaning_reconciles": counts["valid"] - cleaning["exact_duplicates_removed"] == counts["cleaned"],
              "stored_equals_cleaned": counts["cleaned"] == counts["stored"],
              "repeat_load_unchanged": database["first_content_sha256"] == database["second_content_sha256"] and database["second_load_changes"] == 0}
    if not all(checks.values()):
        raise AssertionError(f"Reconciliation failed: {checks}")
    summary = {"run_id": config["run_id"], "finished_at_utc": now(), "counts": counts, "checks": checks,
               "synthetic_invalid_records_excluded": demonstration["invalid"],
               "differences": f"Validation quarantined {counts['invalid']} rows; cleaning removed {cleaning['exact_duplicates_removed']} exact duplicates. One Kafka end marker is excluded from all record counts."}
    write_json(run_dir / "verification.json", summary)
    write_json(ROOT / "data/latest_run.json", {"run_directory": run_dir.relative_to(ROOT).as_posix()})
    print("Pipeline record counts:", flush=True)
    for stage, count in counts.items():
        print(f"  {stage}: {count}", flush=True)
    print("Second SQLite load changes:", database["second_load_changes"], flush=True)
    print("Synthetic invalid examples rejected:", demonstration["invalid"], flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, help="Replay a preserved complete API collection through real Kafka")
    parser.add_argument("--bootstrap", default="localhost:9092")
    parser.add_argument("--prepare-only", action="store_true", help="Prepare run.json for separate manual producer/consumer commands")
    parser.add_argument("--process-run", type=Path, help="Process an already consumed run")
    args = parser.parse_args()
    if args.process_run:
        process(args.process_run.resolve())
        return
    raw_directory = args.raw_dir
    if raw_directory is None:
        raw_directory = ROOT / "data/raw" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6])
        collect(raw_directory)
    run_dir = prepare(raw_directory, args.bootstrap)
    print(f"RUN_DIR={run_dir.relative_to(ROOT).as_posix()}", flush=True)
    if args.prepare_only:
        return
    try:
        for module in ["src.producer", "src.consumer"]:
            subprocess.run([sys.executable, "-m", module, "--run-dir", str(run_dir)], check=True, cwd=ROOT, timeout=180)
        process(run_dir)
    except Exception as error:
        write_json(run_dir / "FAILED.json", {"error": str(error), "at_utc": now()})
        raise


if __name__ == "__main__":
    main()
