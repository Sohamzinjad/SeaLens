# SeaLens scalability audit

This is a local developer-machine smoke measurement, not a production load test. The server was started with the project's development command and all results were in-memory/local-cache paths.

| Endpoint | 10-request p50 | 10-request p95 | Notes |
| --- | ---: | ---: | --- |
| `/api/health` | 0.7 ms | 15.3 ms | Small status response. |
| `/api/scenarios` | 0.8 ms | 1.0 ms | Seven authored scenario summaries. |
| `/api/scenario/scenario_alpha_rogue_tanker` | 1.3 ms | 2.5 ms | Full in-memory scenario serialization. |
| `/api/dossier/scenario_alpha_rogue_tanker/markdown` | 0.8 ms | 1.0 ms | In-memory dossier generation. |
| `/api/drift_simulation/scenario_alpha_rogue_tanker` | 0.7 ms | 1.0 ms | Short modelled trajectory. |

With 10 concurrent workers and 20 health requests, `/api/health` measured p50 3.3 ms, p95 5.9 ms, maximum 6.0 ms.

## Findings

1. The ordinary scenario endpoints are suitable for the current demo scale, not an operational fleet scale. Scenario data is loaded in process and repeated derived work is not queued or stored in a spatial database.
2. NOAA AIS daily archives are large and the current import runs synchronously in the web request. The audit reproduced a request that did not finish before its 180-second safe client timeout; while it runs, the single development worker cannot serve other requests. Move archive import/crop/analysis into background jobs before multi-user use.
3. Large GeoTIFF reads, U-Net inference, CA-CFAR, and live-provider calls need explicit worker limits, task progress, retries, disk quotas, and cache eviction. None of those are a substitute for provenance labels.
4. A deployment target should use multiple application workers behind a reverse proxy, object storage for raster/AIS artifacts, and PostGIS (or equivalent) for vessel tracks and spatial/time queries. Load-test against a fixed hardware profile before claiming capacity.
5. Cache keys and audit records exist, but cache retention, maximum sizes, and operational telemetry need configuration and monitoring before production.

