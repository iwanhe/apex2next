# Infrastructure

- `docker/`: container build assets.
- `local/`: local developer environment and Compose overrides.
- `cloud/`: cloud deployment reference architecture and IaC.

Keep secrets out of source control. Local Compose is for development only; production must use managed secrets, TLS, backups, network isolation, and monitored services.
