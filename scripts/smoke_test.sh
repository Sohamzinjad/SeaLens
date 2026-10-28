#!/bin/bash
echo "=== seaLens Smoke Test ==="
echo "Testing API health..."
curl -s http://localhost:8000/api/health | python3 -m json.tool || echo "FAILED"
echo -e "\n\nTesting scenario load..."
curl -s http://localhost:8000/api/scenario/scenario_wakashio_validation | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK:', d['id'])" || echo "FAILED"
echo -e "\n\nTesting dossier..."
curl -s http://localhost:8000/api/dossier/scenario_wakashio_validation/markdown | head -5 || echo "FAILED"
echo -e "\n\n=== Smoke Test Complete ==="
