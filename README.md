# Content Audit Platform

A Chinese content audit platform with FastAPI, SQLite, layered audit engines, and a static web console.

## Run

```bash
python -m pip install -e .[dev]
uvicorn audit.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

On first startup, the app initializes SQLite at `./data/audit.db` and imports builtin words from `./seeds/sensitive_words.csv`.

DeepSeek is optional for local demo. If `DEEPSEEK_API_KEY` is empty, L3 returns a degraded `l3_error` result while L1/L2/L4 continue to work.

## Verify

```bash
python -m pytest tests/unit tests/property tests/integration -q
python -m compileall -q src/audit
```
