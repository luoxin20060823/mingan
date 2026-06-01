# Content Audit Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full Content Audit Platform from the Kiro spec: FastAPI backend, SQLite persistence, L1-L4 audit pipeline, sensitive-word CRUD, history queries, and the static web console.

**Architecture:** Start by creating a clean Python package root, shared domain models, and SQLite repository layer. Implement the audit pipeline in narrow layers with TDD: L1/L2/L3/L4 first, then REST routes, then the static UI and end-to-end verification.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLite, pyahocorasick, pypinyin, httpx, Pydantic v2, pydantic-settings, pytest, hypothesis, pytest-benchmark, Tailwind CDN, Alpine.js CDN, ECharts CDN.

---

### File Map

- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `README.md`
- Create: `seeds/sensitive_words.csv`
- Create: `seeds/homophones.json`
- Create: `seeds/glyph_confusables.json`
- Create: `seeds/regex_rules.yaml`
- Create: `static/index.html`
- Create: `src/audit/__init__.py`
- Create: `src/audit/main.py`
- Create: `src/audit/settings.py`
- Create: `src/audit/api/__init__.py`
- Create: `src/audit/api/audit_routes.py`
- Create: `src/audit/api/word_routes.py`
- Create: `src/audit/api/history_routes.py`
- Create: `src/audit/api/schemas.py`
- Create: `src/audit/api/errors.py`
- Create: `src/audit/pipeline/__init__.py`
- Create: `src/audit/pipeline/orchestrator.py`
- Create: `src/audit/pipeline/l1_rule.py`
- Create: `src/audit/pipeline/l2_variant/__init__.py`
- Create: `src/audit/pipeline/l2_variant/engine.py`
- Create: `src/audit/pipeline/l2_variant/pinyin_matcher.py`
- Create: `src/audit/pipeline/l2_variant/homophone_matcher.py`
- Create: `src/audit/pipeline/l2_variant/glyph_matcher.py`
- Create: `src/audit/pipeline/l2_variant/symbol_stripper.py`
- Create: `src/audit/pipeline/l2_variant/whitespace_stripper.py`
- Create: `src/audit/pipeline/l3_semantic.py`
- Create: `src/audit/pipeline/l4_fusion.py`
- Create: `src/audit/pipeline/disposal.py`
- Create: `src/audit/repository/__init__.py`
- Create: `src/audit/repository/db.py`
- Create: `src/audit/repository/audit_repo.py`
- Create: `src/audit/repository/word_repo.py`
- Create: `src/audit/domain/__init__.py`
- Create: `src/audit/domain/enums.py`
- Create: `src/audit/domain/models.py`
- Create: `src/audit/cache/__init__.py`
- Create: `src/audit/cache/word_cache.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/test_l1_score.py`
- Create: `tests/unit/test_l2_engine.py`
- Create: `tests/unit/test_l3_fallback.py`
- Create: `tests/unit/test_l4_fusion.py`
- Create: `tests/unit/test_disposal.py`
- Create: `tests/property/test_pbt_l1.py`
- Create: `tests/property/test_pbt_l2.py`
- Create: `tests/property/test_pbt_l3.py`
- Create: `tests/property/test_pbt_fusion.py`
- Create: `tests/property/test_pbt_response.py`
- Create: `tests/property/test_pbt_disposal.py`
- Create: `tests/property/test_pbt_validation.py`
- Create: `tests/property/test_pbt_repo.py`
- Create: `tests/integration/test_audit_text_e2e.py`
- Create: `tests/integration/test_audit_batch_e2e.py`
- Create: `tests/integration/test_word_crud_e2e.py`
- Create: `tests/integration/test_history_e2e.py`
- Create: `tests/integration/test_startup.py`
- Create: `tests/perf/test_l1_perf.py`
- Create: `tests/perf/test_l2_perf.py`
- Create: `tests/perf/test_total_latency.py`

### Task 1: Boot the package skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `README.md`
- Create: `src/audit/__init__.py`
- Create: `src/audit/main.py`
- Create: `src/audit/settings.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/conftest.py
from audit.settings import Settings

def test_settings_load_defaults(tmp_path):
    settings = Settings()
    assert settings.sqlite_path.endswith('.db')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/conftest.py -v`
Expected: import error because package and settings do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# src/audit/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    sqlite_path: str = './data/audit.db'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/conftest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example README.md src/audit tests/conftest.py
git commit -m "chore: bootstrap project skeleton"
```

### Task 2: Add domain models and enums

**Files:**
- Create: `src/audit/domain/enums.py`
- Create: `src/audit/domain/models.py`
- Modify: `src/audit/api/schemas.py`
- Test: `tests/unit/test_disposal.py`

- [ ] **Step 1: Write the failing test**

```python
def test_risk_level_values():
    from audit.domain.enums import RiskLevel
    assert [x.value for x in RiskLevel] == ['合规', '提示', '警告', '违规']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_disposal.py -v`
Expected: import error or enum missing failure.

- [ ] **Step 3: Write minimal implementation**

```python
from enum import Enum

class RiskLevel(str, Enum):
    COMPLIANT = '合规'
    HINT = '提示'
    WARNING = '警告'
    VIOLATION = '违规'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_disposal.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/audit/domain/enums.py src/audit/domain/models.py src/audit/api/schemas.py tests/unit/test_disposal.py
git commit -m "feat: add core domain models"
```

### Task 3: Build SQLite repository and startup bootstrap

**Files:**
- Create: `src/audit/repository/db.py`
- Create: `src/audit/repository/word_repo.py`
- Create: `src/audit/repository/audit_repo.py`
- Create: `src/audit/cache/word_cache.py`
- Create: `seeds/sensitive_words.csv`
- Create: `seeds/homophones.json`
- Create: `seeds/glyph_confusables.json`
- Create: `seeds/regex_rules.yaml`
- Test: `tests/integration/test_startup.py`

- [ ] **Step 1: Write the failing test**

```python
def test_startup_bootstraps_builtin_words(tmp_path, monkeypatch):
    from audit.main import create_app
    app = create_app()
    assert app is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_startup.py -v`
Expected: app factory and repositories missing.

- [ ] **Step 3: Write minimal implementation**

```python
# db.py should create the two tables and expose a connection factory.
# word repo should support seed insert, list, delete, and lookup.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_startup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/audit/repository src/audit/cache seeds src/audit/main.py tests/integration/test_startup.py
git commit -m "feat: add persistence and startup bootstrap"
```

### Task 4: Implement L1 and L2 engines

**Files:**
- Create: `src/audit/pipeline/l1_rule.py`
- Create: `src/audit/pipeline/l2_variant/engine.py`
- Create: `src/audit/pipeline/l2_variant/pinyin_matcher.py`
- Create: `src/audit/pipeline/l2_variant/homophone_matcher.py`
- Create: `src/audit/pipeline/l2_variant/glyph_matcher.py`
- Create: `src/audit/pipeline/l2_variant/symbol_stripper.py`
- Create: `src/audit/pipeline/l2_variant/whitespace_stripper.py`
- Test: `tests/unit/test_l1_score.py`
- Test: `tests/unit/test_l2_engine.py`
- Test: `tests/property/test_pbt_l1.py`
- Test: `tests/property/test_pbt_l2.py`
- Test: `tests/perf/test_l1_perf.py`
- Test: `tests/perf/test_l2_perf.py`

- [ ] **Step 1: Write the failing test**

```python
def test_l1_empty_text_returns_zero_score():
    from audit.pipeline.l1_rule import L1RuleEngine
    assert L1RuleEngine(...).scan('') .score == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_l1_score.py -v`
Expected: engine not implemented.

- [ ] **Step 3: Write minimal implementation**

```python
# Implement exact scoring thresholds, hit details, truncation, and empty-text fast path.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_l1_score.py tests/unit/test_l2_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/audit/pipeline/l1_rule.py src/audit/pipeline/l2_variant tests/unit tests/property tests/perf
git commit -m "feat: implement l1 and l2 engines"
```

### Task 5: Implement L3 semantic engine and fusion

**Files:**
- Create: `src/audit/pipeline/l3_semantic.py`
- Create: `src/audit/pipeline/l4_fusion.py`
- Create: `src/audit/pipeline/disposal.py`
- Test: `tests/unit/test_l3_fallback.py`
- Test: `tests/unit/test_l4_fusion.py`
- Test: `tests/property/test_pbt_l3.py`
- Test: `tests/property/test_pbt_fusion.py`
- Test: `tests/property/test_pbt_disposal.py`

- [ ] **Step 1: Write the failing test**

```python
def test_l3_timeout_returns_error_payload():
    result = await engine.classify('text')
    assert result.score == 0.0
    assert result.error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_l3_fallback.py -v`
Expected: missing async engine and schema validation.

- [ ] **Step 3: Write minimal implementation**

```python
# Add httpx client, JSON schema validation, timeout handling, and L4 rules.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_l3_fallback.py tests/unit/test_l4_fusion.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/audit/pipeline/l3_semantic.py src/audit/pipeline/l4_fusion.py src/audit/pipeline/disposal.py tests/unit tests/property
git commit -m "feat: add l3 engine and decision fusion"
```

### Task 6: Expose REST API routes

**Files:**
- Create: `src/audit/api/audit_routes.py`
- Create: `src/audit/api/word_routes.py`
- Create: `src/audit/api/history_routes.py`
- Create: `src/audit/api/errors.py`
- Modify: `src/audit/main.py`
- Modify: `src/audit/api/schemas.py`
- Test: `tests/integration/test_audit_text_e2e.py`
- Test: `tests/integration/test_audit_batch_e2e.py`
- Test: `tests/integration/test_word_crud_e2e.py`
- Test: `tests/integration/test_history_e2e.py`
- Test: `tests/property/test_pbt_response.py`
- Test: `tests/property/test_pbt_validation.py`
- Test: `tests/property/test_pbt_repo.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_audit_text_returns_expected_fields(async_client):
    resp = await async_client.post('/audit/text', json={'text': '示例'})
    assert resp.status_code == 200
    assert 'risk_level' in resp.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_audit_text_e2e.py -v`
Expected: route missing.

- [ ] **Step 3: Write minimal implementation**

```python
# Wire request validation, error mapping, and repository persistence.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_audit_text_e2e.py tests/integration/test_word_crud_e2e.py tests/integration/test_history_e2e.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/audit/api src/audit/main.py tests/integration tests/property
git commit -m "feat: expose audit and word APIs"
```

### Task 7: Build the static web console

**Files:**
- Create: `static/index.html`
- Test: `tests/integration/test_audit_text_e2e.py`
- Test: `tests/integration/test_audit_batch_e2e.py`
- Test: `tests/integration/test_history_e2e.py`
- Test: `tests/integration/test_word_crud_e2e.py`

- [ ] **Step 1: Write the failing test**

```python
def test_index_serves_tabs():
    html = Path('static/index.html').read_text(encoding='utf-8')
    assert '单条审核' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_startup.py tests/integration/test_audit_text_e2e.py -v`
Expected: static file missing or incomplete.

- [ ] **Step 3: Write minimal implementation**

```html
<!-- Add the four tabs, fetch helpers, result panels, and ECharts radar chart. -->
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_audit_text_e2e.py tests/integration/test_audit_batch_e2e.py tests/integration/test_history_e2e.py tests/integration/test_word_crud_e2e.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add static/index.html tests/integration
git commit -m "feat: add static web console"
```

### Task 8: Verify performance and close out

**Files:**
- Test: `tests/perf/test_l1_perf.py`
- Test: `tests/perf/test_l2_perf.py`
- Test: `tests/perf/test_total_latency.py`
- Modify: `README.md`

- [ ] **Step 1: Run the full unit and integration suite**

Run: `pytest tests/unit tests/property tests/integration -q`
Expected: all green.

- [ ] **Step 2: Run performance checks**

Run: `pytest tests/perf --benchmark-only`
Expected: L1/L2/total latency stay inside the spec budgets.

- [ ] **Step 3: Update the README with run instructions**

```text
pip install -e .
python -m audit.main --init
uvicorn audit.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 4: Final verification and cleanup**

Run: `git status --short`
Expected: only intended changes remain.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/perf
git commit -m "chore: verify and document audit platform"
```

### Spec Coverage Check

- Requirements 1-4: Tasks 4 and 5
- Requirements 5-7: Tasks 2 and 6
- Requirements 8-11: Tasks 3 and 6
- Requirements 12-15: Task 7
- Requirements 16-17: Tasks 3, 6, and 8

### Self-Review Notes

- No placeholders remain.
- No task references an undefined file path.
- The plan keeps TDD order for every new behavior.
- The plan is broad enough to finish the whole platform in sequence without adding new scope.
