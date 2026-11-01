# Real-SAR benchmark intake

Do not claim real-data precision, recall, IoU, or false-positive rate until a
labelled benchmark with a documented licence and annotation protocol is added.

Create a `manifest.json` next to masks using:

```json
{
  "source": "documented authorised dataset name and licence",
  "samples": [{
    "id": "scene-001",
    "prediction_mask": "predictions/scene-001.png",
    "ground_truth_mask": "labels/scene-001.png"
  }]
}
```

Then run `python -m ml_engine.evaluate_benchmark data/benchmarks/manifest.json`.
The evaluator reports pixel-level precision, recall, IoU, and false-positive
rate. It does not validate label quality or operational performance.
