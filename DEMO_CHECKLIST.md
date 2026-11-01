# Demo Checklist & Rehearsal Guide

## Pre-Demo (0-5 min)
- [ ] Run `python3 start.py` and wait for server to start
- [ ] Run `./scripts/smoke_test.sh` to verify endpoints
- [ ] Open http://localhost:8000/c2
- [ ] Check health page at http://localhost:8000/health
- [ ] Verify that simulated scenarios are visibly labelled before demonstrating without network access

## Demo Flow (0-150s)
### 0-30s: Context
- [ ] Show landing page / explain problem statement (SIH #143 NTRO)
- [ ] Point to architecture: SAR → backtrack → AIS → dossier

### 30-60s: SAR Detection
- [ ] Select case (Wakashio validation or demo)
- [ ] Run SAR / Show slick detection
- [ ] Point out confidence, look-alike filtering

### 60-90s: AIS Correlation
- [ ] Show vessel tracks
- [ ] Import NOAA AIS or show existing
- [ ] Highlight dark vessels if present

### 90-120s: Backtrack & Attribution
- [ ] Run GFS wind backtracking
- [ ] Show origin cone / uncertainty
- [ ] Review ranked vessel leads with scores

### 120-150s: Dossier & Transparency
- [ ] Generate forensic dossier
- [ ] Show data sources, timestamps, cache, uncertainty warnings
- [ ] Emphasize: "Investigative leads only, not proof"

## Post-Demo
- [ ] Show Model Card for transparency
- [ ] Answer questions using docs
