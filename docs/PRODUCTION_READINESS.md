# Production-readiness roadmap

SeaLens is a local research/demo prototype. The following foundations are now
present: request validation, allow-listed public download sources, file hashes,
audit logging, configurable CORS, optional API-key enforcement, basic in-memory
rate limiting, source provenance, and an in-process queue for slow public-data
downloads.

Before a real multi-user or enforcement deployment:

1. Replace `LocalJobManager` with a durable worker/queue and persistent job
   status store; add cancellation and progress reporting from the downloader.
2. Deploy PostGIS with managed credentials, migrations, retention policies,
   backups, and spatial/time indexes. `docker-compose.postgis.yml` is local
   development scaffolding, not a production password policy.
3. Use server-side identity/OIDC, scoped roles, hashed API keys, HTTPS, trusted
   proxy configuration, secrets management, and central audit/error monitoring.
4. Place object storage and quotas in front of SAR/AIS artifacts; add antivirus
   and content validation for all user-supplied files.
5. Run independent model validation on a licensed, labelled real-SAR benchmark
   before publishing performance claims. The committed U-Net checkpoint has no
   verified real-data training or test metrics.
6. Replace the duplicated C2 source document with a component-based frontend;
   runtime selection of one duplicate is a compatibility workaround, not a
   maintainable production architecture.
