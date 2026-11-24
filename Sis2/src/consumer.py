"""Consume one isolated topic in sequence, checking its end marker and payload hash."""
import argparse
import json
import time
from pathlib import Path

from confluent_kafka import Consumer, TopicPartition

from .common import digest, now, read_json, write_json


def consume(run_dir, timeout=120):
    config = read_json(run_dir / "run.json")
    consumer = Consumer({"bootstrap.servers": config["bootstrap"], "broker.address.family": "v4", "group.id": config["run_id"],
                         "enable.auto.commit": False, "auto.offset.reset": "earliest"})
    records, offsets = [], []
    result = {"complete": False, "consumed": 0, "topic": config["topic"]}
    try:
        consumer.assign([TopicPartition(config["topic"], 0, 0)])
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                raise RuntimeError(str(message.error()))
            payload = json.loads(message.value().decode("utf-8"))
            if payload["run_id"] != config["run_id"]:
                raise ValueError("Foreign run found in isolated topic")
            if payload["kind"] == "end":
                actual_hash = digest(records)
                if len(records) != config["expected"] or payload["count"] != len(records):
                    raise ValueError("End marker count mismatch")
                if actual_hash != payload["sha256"] or actual_hash != config["records_sha256"]:
                    raise ValueError("Consumed content differs from original data")
                write_json(run_dir / "consumed.json", records)
                result.update(complete=True, consumed=len(records), records_sha256=actual_hash,
                              offsets=offsets, end_marker_offset=message.offset())
                print(f"Consumed and verified {len(records)} records (+ 1 end marker)", flush=True)
                return result
            if payload["kind"] != "record" or payload["sequence"] != len(records):
                raise ValueError("Missing, repeated, or out-of-order record")
            records.append(payload["record"])
            offsets.append(message.offset())
        raise TimeoutError(f"No complete stream within {timeout}s; received {len(records)}")
    except Exception as error:
        result.update(error=str(error), consumed=len(records))
        write_json(run_dir / "consumed_partial.json", records)
        raise
    finally:
        consumer.close()
        result["finished_at_utc"] = now()
        write_json(run_dir / "consumer.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    consume(args.run_dir, args.timeout)
