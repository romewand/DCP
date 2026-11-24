"""Publish a finite JSON stream to a new topic, recording broker acknowledgements."""
import argparse
import json
from pathlib import Path

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from .common import ROOT, digest, now, read_json, write_json


def publish(run_dir):
    config = read_json(run_dir / "run.json")
    records = read_json(ROOT / config["raw_directory"] / "records.json")
    if len(records) != config["expected"] or digest(records) != config["records_sha256"]:
        raise ValueError("Raw records differ from the collection manifest")
    topic = config["topic"]
    admin = AdminClient({"bootstrap.servers": config["bootstrap"], "broker.address.family": "v4"})
    # Reusing a topic could duplicate a finite run. A fresh run always has a fresh topic.
    try:
        admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])[topic].result(timeout=30)
    except TimeoutError as error:
        raise RuntimeError("Kafka did not respond. Start Docker Desktop and run docker compose up -d --wait.") from error
    producer = Producer({"bootstrap.servers": config["bootstrap"], "broker.address.family": "v4", "enable.idempotence": True,
                         "acks": "all", "delivery.timeout.ms": 30000})
    acknowledgements, errors = [], []

    def delivered(error, message):
        if error:
            errors.append(str(error))
        else:
            acknowledgements.append({"partition": message.partition(), "offset": message.offset()})

    for sequence, record in enumerate(records):
        value = {"run_id": config["run_id"], "kind": "record", "sequence": sequence, "record": record}
        producer.produce(topic, partition=0, key=str(record["FHRSID"]),
                         value=json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"), callback=delivered)
        producer.poll(0)
    pending = producer.flush(40)
    result = {"finished_at_utc": now(), "topic": topic, "published": len(acknowledgements),
              "pending": pending, "errors": errors, "acknowledgements": acknowledgements}
    write_json(run_dir / "producer.json", result)
    if pending or errors or len(acknowledgements) != len(records):
        raise RuntimeError("Not all data messages were acknowledged")
    end_errors = []

    def end_delivered(error, message):
        if error:
            end_errors.append(str(error))

    end = {"kind": "end", "run_id": config["run_id"], "count": len(records), "sha256": digest(records)}
    producer.produce(topic, partition=0, value=json.dumps(end).encode("utf-8"),
                     callback=end_delivered)
    if producer.flush(40) or end_errors:
        raise RuntimeError(f"End marker delivery failed: {end_errors}")
    result["end_marker_acknowledged"] = True
    write_json(run_dir / "producer.json", result)
    print(f"Published and acknowledged {len(records)} records (+ 1 end marker)", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    publish(parser.parse_args().run_dir)
