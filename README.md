# 🌊 seaLens: AI Maritime Domain Awareness & C2 System
> **SIH Problem #143 (NTRO - National Technical Research Organisation)**  
> *Satellite Synthetic Aperture Radar (SAR) Oil Spill Detection, Dark Vessel Correlation & Reverse Drift Intelligence System*

## Quick Start
```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
python3 start.py  # http://localhost:8000, /c2, /docs, /health
```

## Key Features
- SAR detection (U-Net/CFAR), look-alike rejection
- Reverse/backtrack drift with uncertainty cones, GFS/Copernicus provenance
- AIS correlation, dark vessel detection, repeat offenders
- Real Data Mode and clearly labelled simulated scenarios for network-free demonstrations
- Forensic dossier with sources/timestamps/cache/uncertainty
- Guided demo flow with toasts, reset, URL auto-demoing

## Demo Links
- C2: http://localhost:8000/c2
- Auto-demo: http://localhost:8000/c2?demo=1&case=wakashio
- Health: http://localhost:8000/health

## Documentation
- [DEMO_FLOW.md](DEMO_FLOW.md) - Rehearsed demo sequence
- [ARCHITECTURE_WORKFLOW.md](ARCHITECTURE_WORKFLOW.md) - SAR → backtrack → AIS → dossier
- [MODEL_TRANSPARENCY.md](MODEL_TRANSPARENCY.md) - Model limitations
- [MODEL_VALIDATION.md](MODEL_VALIDATION.md) - Validation checklist
- [evaluation/EVALUATION_TEMPLATE.md](evaluation/EVALUATION_TEMPLATE.md) - Metrics template
- [data/dataset_manifest.json](data/dataset_manifest.json) - Dataset tracking

## Important Note
All detections and prioritization are **probabilistic investigative leads, not proof of responsibility**.
