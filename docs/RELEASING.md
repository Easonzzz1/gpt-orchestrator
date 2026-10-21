# Releasing

Review the public diff and upstream license notices. Run `sh scripts/check.sh`; verify installer idempotence and offline route/brief commands in a fresh local checkout. Keep state, logs, configurations and browser profiles out of the release.

Record actual checks and untested integrations. Publish a tag only for the verified commit. Never present synthetic fixtures or a fake executor as real model validation.
