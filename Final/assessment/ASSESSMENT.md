# Final project source assessment — 17 November 2026

**Verdict: NASA PSCompPars is technically suitable for the Final project.** Actual Selenium extraction passed the dynamic-content and minimum cleaned-size checks. This assessment does not claim that the complete Final pipeline, Airflow execution or submission requirements are finished.

## Evidence from the actual website

- Tested the PSCompPars interactive table in headless Chrome using the existing DCP Selenium installation.
- The table displayed 6,470 total planets at the time of testing.
- A separate JavaScript-disabled browser rendered zero planet links in the data grid.
- Selenium scrolled the grid 16 times and read dynamically rendered DOM cells. No requests to TAP, the data API, or a CSV download endpoint were made by the assessment scripts. The website's own background requests are part of its normal JavaScript rendering.
- The test retained 308 distinct planet names and 308 records after basic identity checks, whitespace normalization and type conversion. No core identity rows were rejected.
- Repeated observations of rows during scrolling were deduplicated by planet name. These overlaps are a scraping artifact, not evidence that the source catalogue contains duplicate planets.
- Seven discovery methods and discovery years from 1995 to 2026 occurred in the sample.
- This alphabetical prefix is a feasibility sample, not a complete catalogue or representative scientific sample. Full-table traversal has not been tested.

Files: `selenium_raw_sample.json` preserves rendered cell text/HTML and asymmetric error spans; `cleaned_sample.json` contains the provisional parsed sample; `sample_profile.json` contains measured counts; `javascript_disabled.json` records the disabled-JavaScript result; screenshots show the initial and scrolled table. `sample_test.py` is an assessment probe, not the finished submission scraper.

## Assignment requirement mapping

The actual source checked was `Downloads/Final project_Assignment.pdf` (three pages).

| Requirement | Assessment |
|---|---|
| Dynamic JavaScript website | Confirmed by successful rendered grid and zero grid planet links with JavaScript disabled. |
| Selenium or Playwright | Confirmed using Selenium, including explicit waits and scrolling. |
| Meaningful structured records | Confirmed: one planet, host, discovery information and physical measurements per record. |
| At least 200 records after cleaning | Confirmed for the pilot: 308 retained. Production must assert this again on each successful run. |
| Duplicate removal | Scroll overlap is present and handled. Full-catalogue duplicate/conflict checks remain necessary. |
| Missing-value handling | Real missing scientific measurements exist; retain them as null rather than inventing values. |
| Text normalization and type conversion | Feasible and demonstrated in the pilot. Scientific cell parsing needs more complete tests before production. |
| SQLite schema and insertion | Compatible with TEXT/INTEGER/REAL columns and nullable measurements; not implemented or executed for this Final assessment. |
| Airflow scraping -> cleaning -> loading | Suitable architecture; no Final DAG has been implemented or successfully run yet. |
| Schedule no more than once per 24 hours | Use a fixed daily UTC schedule, catchup=False and max_active_runs=1. Do not use frequent schedules or backfills. |
| Logging and retries | Must be implemented at each production stage; save row counts, failure screenshots, attempts and database verification. |
| At least one successful Airflow run | Still required. Selenium feasibility is not proof of DAG execution. |
| Website different from other groups | Cannot establish locally; instructor registration is necessary. |
| Website not used during practical sessions | No exoplanetarchive reference found in local prac1–prac8 Python/notebook/Markdown files. This cannot establish what was used in every classroom session. |
| Repository access, report and defence | Still required for Final. SIS2 artifacts do not satisfy these requirements for Final. |

The assignment contains a written AI restriction; the user previously reported subsequent instructor permission. Assistance should remain accurately disclosed, and any permission limited specifically to SIS2 should not be assumed to cover Final.

## Data quality and scientific meaning

Observed missing measurements among the 308 sample planets:

| Field | Missing |
|---|---:|
| Orbital period | 25 |
| Semi-major axis | 34 |
| Planet radius (Earth units) | 5 |
| Eccentricity | 74 |
| Equilibrium temperature | 31 |
| Stellar effective temperature | 5 |
| Distance | 4 |

Planet name, host, star/planet counts, discovery method/year/facility, controversy flag and mass provenance were populated in this sample. This is not a guarantee of completeness in the full table.

The selected numerical cells included 27 upper/lower-limit expressions. Preserve the comparison operator separately: `<3464` must not become an ordinary exact mass of 3464. Uncertainties can appear as ± values or as separate upper/lower HTML spans. Preserve raw text and parse value, uncertainty and limit fields separately. The pilot extracts central values and limit signs while retaining raw uncertainty text/HTML; it does not finish all uncertainty normalization.

Observed mass provenance includes Mass, Msini, Msin(i)/sin(i), and M-R relationship. These must not be treated as identical direct mass measurements. Keep provenance when analysing or updating the catalogue. Keep units in column names and document them. Missing values are not zero; a controversy flag of zero and an eccentricity of zero can be legitimate.

NASA describes PSCompPars as one row per planet, combining information across references. That makes it a good catalogue source, but the resulting physical parameters may not form a single self-consistent scientific solution. Keep the controversy flag rather than silently assuming every confirmation is undisputed.

## Recommended collection scope and implementation

Use the full PSCompPars inventory for a project titled an automated confirmed-exoplanet catalogue. A named, justified subset could meet the assignment, but a first-alphabetical-prefix sample should not be labelled a complete catalogue.

Select about 12–17 useful fields: planet/host names, discovery method/year/facility, system star/planet counts, controversy flag, orbital period, Earth radius, Earth mass, mass provenance, eccentricity, stellar temperature and distance. Add a collection timestamp generated by the scraper. Discovery year is an integer year, not a complete observation timestamp. Archive update dates are optional; their UI selection and extraction were not tested here.

For the final scraper:

1. Open a fresh browser session, verify PSCompPars and wait for nonempty grid rows.
2. Map columns from rendered headers, not fixed positional assumptions. The probe's observed 35-cell layout is not a durable production contract.
3. Scroll the actual grid with overlapping steps and wait for changed row content. Reacquire DOM elements after refreshes. Never assume all rows are already present in the first page source.
4. Preserve raw cells and deduplicate observations using planet identity. Detect conflicting repeated values instead of silently taking an arbitrary one.
5. Stop only at a verified end of table and reconcile unique collected identities with the displayed total. Report incomplete traversals and do not replace the previous good database snapshot.
6. Clean and validate types, missing values, limits, uncertainty structure and units. Log counts before/after each decision.
7. Load a SQLite current-catalogue table in a transaction. Use planet name as a provisional natural key, retain source URL/collection time and use upserts for revised values. Handle renamed or removed entries explicitly; a name is not an immutable identifier. Consider storing complete run snapshots for change history.
8. Run scraping, cleaning and loading as separate Airflow tasks. Pass file paths/run IDs between tasks rather than a large DataFrame. Keep artifacts/database in a persistent mounted directory.

Do not substitute direct API calls, TAP queries, hidden application data stores, or a bulk CSV download for DOM extraction. Browser use solely to discover an API URL would not satisfy the requested approach.

Use Airflow in Linux containers or WSL2 on Windows, with the browser and driver available inside the scraping task's execution environment. The successful Windows Selenium probe does not prove that container setup. A daily run may legitimately find no changes; log this without inventing updates. Use bounded retries and avoid overlapping runs.

## References

- Interactive source: https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=PSCompPars
- Field definitions: https://exoplanetarchive.ipac.caltech.edu/docs/API_PS_columns.html
- Interactive table guide: https://exoplanetarchive.ipac.caltech.edu/docs/ICEexohelp.html
- Selenium waits: https://www.selenium.dev/documentation/webdriver/waits/
- Airflow prerequisites: https://airflow.apache.org/docs/apache-airflow/stable/installation/prerequisites.html

SIS2 remains the Food Standards Agency API project. Final uses the NASA interactive website and a separate Selenium/Airflow pipeline.
