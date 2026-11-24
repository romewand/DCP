# SIS2: food hygiene data pipeline

Uteuliyeva Gauhar — individual project, Data Collection & Preparation.

This project compares food hygiene ratings across business types in Leeds and York. It collects FSA API records, sends them through Kafka, validates them with Pandera, cleans them with pandas/NumPy, stores them in SQLite and produces three charts.

## Setup

Requirements: Python 3.14, Docker Desktop using Linux containers, and internet access for installation or a fresh API collection. No API key is required.

From the cloned DCP repository in PowerShell:

```powershell
cd Sis2
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d --wait
```

On Linux/macOS, use `python3.14`, `python3.14 -m venv .venv`, and `.venv/bin/python` instead of the Windows interpreter path. Run subsequent commands from Sis2.

## Run the whole pipeline

Replay the included collection through a real Kafka broker:

```powershell
.\.venv\Scripts\python.exe main.py --raw-dir data/raw/2026-11-16-complete
```

To collect new API data instead:

```powershell
.\.venv\Scripts\python.exe main.py
```

The preserved collection is from 16 November 2026 and contains 9,882 records: 7,685 from Leeds and 2,197 from York. A new live collection can have different results. Every run creates a new topic and output directory. The consumer stops at a verified end marker or fails after its timeout; the control message is excluded from business-record counts. Only a successful run updates `data/latest_run.json`.

## Run producer and consumer separately

First prepare a new run and copy its printed RUN_DIR value:

```powershell
.\.venv\Scripts\python.exe main.py --raw-dir data/raw/2026-11-16-complete --prepare-only
$runDir = 'data/runs/REPLACE_WITH_PRINTED_RUN_DIRECTORY'
.\.venv\Scripts\python.exe -m src.producer --run-dir $runDir
.\.venv\Scripts\python.exe -m src.consumer --run-dir $runDir --timeout 120
.\.venv\Scripts\python.exe main.py --process-run $runDir
```

The producer creates one partition and replication factor one for the local broker at localhost:9092. It serializes records to JSON and checks delivery acknowledgements. The consumer reads from offset zero, checks record order and content, and writes the received records. Prepare a new run before repeating the producer; an existing topic is deliberately not reused.

## Check results

```powershell
$runDir = (Get-Content data/latest_run.json -Raw | ConvertFrom-Json).run_directory
Get-Content "$runDir/verification.json"
Get-Content "$runDir/database_verification.json"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
docker compose ps
```

The saved snapshot should produce 9,882 published, consumed, valid, cleaned and stored records, with zero invalid source records. Four separate invalid test records must be rejected. Loading SQLite twice must change zero rows on the second load and preserve all values.

The selected run contains:

- `output.db`: SQLite table `establishments`, with `fhrs_id` as its primary key.
- `cleaned.csv`, grouped statistics and the rating pivot table.
- `figures/`: three generated PNG charts.
- `producer.json`, `consumer.json`, `validation.json`, `cleaning.json` and `verification.json`: stage results.
- `database_verification.json`: SQL query results and repeat-load checks.
- `invalid_demo/`: clearly separated synthetic records and validation errors.

Open `output.db` in a SQLite viewer to execute `sql/verify.sql`. The loading stage also executes those queries automatically. `ON CONFLICT DO NOTHING` prevents duplicate inserts for the same snapshot; it is not an update strategy for changing ratings. Failed runs do not replace the latest successful pointer. Read their error output before retrying with a new run.

Stop the local broker when finished with `docker compose stop`.

## Data source and preparation

The FSA endpoint is `https://api.ratings.food.gov.uk/Establishments`, with headers `x-api-version: 2` and `Accept: application/json`. The collector resolves Leeds and York through `/Authorities`, then requests `schemeTypeKey=FHRS`, `sortOptionKey=alpha`, `pageSize=5000` and consecutive `pageNumber` values. It verifies page totals and unique IDs, preserves original response bodies and retries network/temporary HTTP failures up to three attempts.

Pandera checks IDs, required text, selected authorities, scheme, rating categories, dates, component scores, coordinates and JSON structure before main cleaning. Invalid rows are quarantined; duplicate IDs quarantine all affected rows rather than arbitrarily choosing one. Separate test cases demonstrate validation failures.

Cleaning normalizes whitespace and postcode case, converts types, checks exact duplicates, preserves missing values, sums scores with NumPy and filters low ratings with complete scores. Missing scores and special statuses are never converted to zero. Dates of 1901-01-01 are retained as source text and flagged, but excluded from age calculations as an analytical choice, not an established universal FSA rule. GroupBy and pivot tables support the charts.

The charts compare rating distributions, low-rating shares by business type and median component scores by rating. The business-type chart requires at least 30 numeric ratings per category as a display rule. Overall ratings increase with better compliance; component scores increase with worse compliance. Comparisons are descriptive, not causal, and two authorities do not represent the whole UK.

## Files and report

`src/` contains the pipeline stages; `main.py` coordinates them. `sql/` contains the schema and checks; `tests/` contains regression tests. `docs/data_dictionary.md` explains stored fields and null handling. The PDF is `report/project_report.pdf`. The report describes the preserved collection and the verified replay; running a new collection does not automatically update the PDF.

## References

- FSA API: https://api.ratings.food.gov.uk/Help/Index
- FSA open data: https://ratings.food.gov.uk/open-data
- Kafka: https://kafka.apache.org/44/getting-started/quickstart/
- Kafka Python client: https://docs.confluent.io/kafka-clients/python/current/overview.html
- Pandera: https://pandera.readthedocs.io/en/stable/lazy_validation.html
- Course: SIS2 assignment; Lecture6, Lecture 9, Lecture10_SQL, Lecture_11.
