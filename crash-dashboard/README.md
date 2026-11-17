# Crash dashboard data

Pulls the public series behind a "how a crash builds" dashboard and turns them into one
`data.json` with readings, dates, sources, verdicts against written trip lines, and
history lines computed from the same series.

- `fetch.py` downloads FRED graph CSVs (no key) and a few Yahoo daily closes into `raw/` (not committed).
- `build.py` writes `data.json`.
- `.github/workflows/crash-data.yml` runs both on weekday mornings and evenings and publishes
  `data.json` to the `crash-data` branch, so the dashboard page can read the newest copy from
  `raw.githubusercontent.com` without any computer being on.

Nothing here touches the theme.
