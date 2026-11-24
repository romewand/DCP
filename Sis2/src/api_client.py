"""Collect every page for selected authorities; retain original HTTP bodies."""
import argparse
import time
from pathlib import Path

import requests

from .common import ROOT, digest, file_hash, now, write_json

BASE = "https://api.ratings.food.gov.uk"


def request_page(session, endpoint, params, destination, log):
    for attempt in range(1, 4):
        entry = {"requested_at_utc": now(), "endpoint": endpoint, "params": params, "attempt": attempt}
        try:
            response = session.get(BASE + endpoint, params=params, timeout=(10, 40))
            entry.update(url=response.url, status_code=response.status_code)
            log.append(entry)
            write_json(destination.parent / "request_log.json", log)
            response.raise_for_status()
            destination.write_bytes(response.content)
            data = response.json()
            entry.update(response_file=destination.name, sha256=file_hash(destination), meta=data.get("meta"))
            write_json(destination.parent / "request_log.json", log)
            return data
        except (requests.RequestException, ValueError) as error:
            entry["error"] = str(error)
            if entry not in log:
                log.append(entry)
            write_json(destination.parent / "request_log.json", log)
            status = entry.get("status_code")
            retryable = status is None or status in (429, 500, 502, 503, 504)
            if not retryable or attempt == 3:
                raise
            time.sleep(2 ** attempt)


def collect(output, names=("Leeds", "York"), page_size=5000):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    log, records, coverage = [], [], []
    started = now()
    with requests.Session() as session:
        session.headers.update({"x-api-version": "2", "Accept": "application/json"})
        authorities = request_page(session, "/Authorities", {}, output / "authorities.json", log)["authorities"]
        for name in names:
            matches = [a for a in authorities if a["Name"].casefold() == name.casefold()]
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one authority named {name}")
            authority = matches[0]
            selected, page, expected, pages = [], 1, None, None
            while True:
                params = {"schemeTypeKey": "FHRS", "localAuthorityId": authority["LocalAuthorityId"],
                          "sortOptionKey": "alpha", "pageSize": page_size, "pageNumber": page}
                body = request_page(session, "/Establishments", params, output / f"{name.lower()}_{page:03}.json", log)
                meta, rows = body["meta"], body["establishments"]
                if expected is None:
                    expected, pages = meta["totalCount"], meta["totalPages"]
                if (meta["totalCount"], meta["totalPages"], meta["pageNumber"]) != (expected, pages, page):
                    raise ValueError("Pagination changed during collection; retry in a new output directory")
                if meta["itemCount"] != len(rows) or not rows:
                    raise ValueError("Empty or inconsistent API page")
                if any(r["LocalAuthorityName"] != name for r in rows):
                    raise ValueError("Authority response does not match request")
                selected.extend(rows)
                print(f"{name}: page {page}/{pages}, collected {len(selected)}/{expected}", flush=True)
                if page == pages:
                    break
                page += 1
                time.sleep(0.15)
            unique = len({r["FHRSID"] for r in selected})
            if len(selected) != expected or unique != expected:
                raise ValueError("Incomplete inventory or duplicate IDs across pages; no complete manifest written")
            coverage.append({"authority": name, "query_id": authority["LocalAuthorityId"],
                             "authority_code": str(authority["LocalAuthorityIdCode"]), "pages": pages,
                             "expected": expected, "collected": len(selected), "unique": unique})
            records.extend(selected)
    if len(records) < 200 or len({r["FHRSID"] for r in records}) != len(records):
        raise ValueError("Need at least 200 records with globally unique IDs")
    write_json(output / "records.json", records)
    manifest = {"complete": True, "scope": "Complete paginated FHRS inventories of selected authorities",
                "started_at_utc": started, "finished_at_utc": now(), "count": len(records),
                "records_sha256": digest(records), "coverage": coverage,
                "limitation": "Live API pagination is not a transactional snapshot; equal totals cannot rule out all changes."}
    write_json(output / "collection_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/raw/current")
    parser.add_argument("--authorities", nargs="+", default=["Leeds", "York"])
    parser.add_argument("--page-size", type=int, default=5000)
    args = parser.parse_args()
    collect(args.output, args.authorities, args.page_size)
