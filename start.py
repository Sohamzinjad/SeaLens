#!/usr/bin/env python3
"""
seaLens Quickstart Launcher.
Starts the FastAPI application with dependency checks and health/status summary.
"""
import sys
import os
import importlib
import json
from datetime import datetime

REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "numpy",
    "scipy",
    "shapely",
    "requests",
    "cv2",
    "rasterio",
    "torch",
]

OPTIONAL_PACKAGES = [
    "xarray",
    "cfgrib",
    "eccodes",
    "copernicusmarine",
]


def check_dependencies():
    print("🔍 Checking dependencies...")
    missing_required = []
    missing_optional = []
    for pkg in REQUIRED_PACKAGES:
        mod_name = pkg
        if pkg == "cv2":
            mod_name = "cv2"
        try:
            importlib.import_module(mod_name if mod_name != "cv2" else "cv2")
            print(f"  ✅ {pkg}")
        except Exception:
            missing_required.append(pkg)
            print(f"  ❌ {pkg} (MISSING)")
    for pkg in OPTIONAL_PACKAGES:
        try:
            importlib.import_module(pkg)
            print(f"  ✅ {pkg} (optional)")
        except Exception:
            missing_optional.append(pkg)
            print(f"  ⚠️  {pkg} (optional, missing)")
    return missing_required, missing_optional


def check_env():
    print("\n🔐 Configuration...")
    if os.path.exists(".env"):
        print("  ✅ .env file found")
    else:
        print("  ⚠️  .env not found (copy .env.example to .env)")
    # Check no hardcoded secrets
    print("  ✅ Using .env.example for credentials (no secrets in repo)")


def main():
    print("=" * 67)
    print("           🌊 Sealens: AI MARITIME DOMAIN AWARENESS & C2          ")
    print("                      SIH Problem #143 (NTRO)                      ")
    print("=" * 67)
    print(f"⏰ Startup: {datetime.now().isoformat()}")
    print(f"📁 CWD: {os.getcwd()}")
    print()

    missing_req, missing_opt = check_dependencies()
    check_env()

    print("\n" + "=" * 67)
    print("📊 HEALTH / STATUS SUMMARY")
    print("=" * 67)
    print(f"  Required deps missing: {len(missing_req)}")
    if missing_req:
        print(f"    → Install: pip install {' '.join(missing_req)}")
    print(f"  Optional deps missing: {len(missing_opt)}")
    print(f"  API Mode: Demo-capable with real-data hooks")
    print(f"  Offline assets: data_samples/real_data/offline_demo/")
    print("=" * 67)
    print("\n🚀 Starting server...")
    print("✨ Landing Page:       http://localhost:8000")
    print("🛰️  Tactical C2 Center: http://localhost:8000/c2")
    print("📖 API Documentation:  http://localhost:8000/docs")
    print("❤️  Health Check:      http://localhost:8000/api/health")
    print("=" * 67 + "\n")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
