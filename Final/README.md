# Final: exoplanet catalogue

Status: source feasibility assessment only, not a completed Final project.

assessment/ contains Selenium probes and the saved pilot evidence. See assessment/ASSESSMENT.md for results and remaining requirements. The production scraper, SQLite loading, Airflow DAG and successful scheduled execution are still outstanding.

For the pilot scripts, install Selenium in your Python environment and have Chrome available. Run python assessment/sample_test.py from Final. Scripts read the rendered website DOM; they do not collect through direct API requests. Running them overwrites the pilot outputs, so preserve the supplied evidence first if needed.

The supplied sample is an alphabetical feasibility subset, not the complete catalogue. Assistance was used during development; review the code and confirm the instructor's applicable permissions before submission.
