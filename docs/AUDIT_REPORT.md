# SeaLens Cleanup and Verification Audit

## Phase 0 — Baseline

| Check | Result | Evidence |
| --- | --- | --- |
| Working tree before audit | PASS | `git status --short --branch` reported `main...origin/main` with no local changes. |
| Python interpreters | PARTIAL | `python3 --version` and `.venv/bin/python --version` reported Python 3.14.7. No `python3.13` executable was installed, so a <=3.13 compatibility run was not possible on this Mac. |
| Requirements | PASS | `.venv/bin/python -m pip install -r requirements.txt -q` completed successfully. |
| Full test suite | PASS | `.venv/bin/python -m pytest tests tests_api_ui -q`: 29 passed. Torch-dependent tests ran; none were skipped. |
| API baseline | PASS | Started `.venv/bin/python start.py`; `/api/health`, `/api/version`, `/api/scenarios`, and all nine scenario routes for each of seven scenarios returned HTTP 200. Endpoint codes and response sizes were captured during the audit run. |

## Phase 1 — Import and lint check

| Check | Result | Evidence |
| --- | --- | --- |
| Undefined name | FIXED | `backend/services/repeat_offender_engine.py:72` used `Any` without importing it. Added `Any` to its `typing` import. |
| Static lint | PARTIAL | Installed and ran `pyflakes` with `.venv/bin/python -m pyflakes backend ml_engine scripts start.py`. It reported the fixed undefined `Any` plus existing unused-import/local-variable warnings; no other undefined-name warnings were reported. |

### Commands executed

```text
git status --short --branch
python3 --version
python3.13 --version (not installed)
python3.14 --version
.venv/bin/python --version
.venv/bin/python -m pytest tests tests_api_ui -q
.venv/bin/python -m pip install -r requirements.txt -q
.venv/bin/python start.py
curl GET /api/health, /api/version, /api/scenarios and each scenario endpoint
.venv/bin/python -m pip install -q pyflakes
.venv/bin/python -m pyflakes backend ml_engine scripts start.py
```

## Phase 2 — Safe cleanup

| Item | Status | Evidence |
| --- | --- | --- |
| Generated/editor files | DONE | Removed tracked `.DS_Store`, `test_out.pdf`, `pdf_assets/`, runtime `runs/*.json`, and added `runs/` to `.gitignore`. |
| Broken PDF generator | DONE | `generate_pdf_whitepaper.py` compiled but failed to run because `matplotlib` is undeclared/uninstalled; it and its generated assets were removed. |
| Stale checkpoint metadata | DONE | Removed `checkpoints_meta/checkpoint_info.json`; it claimed the checkpoint did not exist. |
| Unused helpers | DONE | Removed unimported `logging_config.py` and `ml_engine/dataset_fetcher.py`. |
| Training-data artifacts | DONE | Removed `data_samples/training_data/`; its manifest had hard-coded `/Users/...` paths and no code/tests referenced it. |
| Placeholder evaluation/training scaffolding | DONE | Removed placeholder evaluation scripts, empty-split verifier, and unused `ml_engine/training/` scaffold. Kept `ml_engine/train_sar_unet.py`, the working synthetic-tile training entry point, and the checkpoint. |
| Model provenance | DONE | Updated `data/dataset_manifest.json` and `model_card.json` to state that the checkpoint training run is not recorded and that the committed trainer generates synthetic tiles. |
| Environment documentation | DONE | Removed unused credentials/settings from `.env.example`; retained Copernicus credentials and CORS origins. |
| Drift fallback documentation | DONE | Corrected `DynamicOceanGridEngine` documentation to say it is modelled, not a real NOAA/Copernicus interpolator. |
| React UI templates | DONE | Verified all 46 `frontend/src/components/ui` files had zero imports; removed them. `npm run build` still passes. |
| Regression gate | PASS | `.venv/bin/python -m pytest tests tests_api_ui -q`: 29 passed; `cd frontend && npm run build`: passed. |

The placeholder evaluation scripts created local JSON files during their audit execution. They are ignored (`evaluation/*.json` and `ml_engine/checkpoints/training_config.json`) and were not committed.

### Additional commands executed

```text
rg reference audits for every deletion candidate
.venv/bin/python <each evaluation/training/verification script> --help
.venv/bin/python -m py_compile generate_pdf_whitepaper.py
.venv/bin/python -c "import generate_pdf_whitepaper as g; g.build_pdf(...)" (failed: matplotlib not installed)
git rm [explicit verified generated/unused targets]
.venv/bin/python -m pytest tests tests_api_ui -q
cd frontend && npm run build
```
