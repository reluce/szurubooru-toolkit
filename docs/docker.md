# Docker and scheduled jobs

## Select an image

Each release publishes image variants for the optional extras. Pick the
smallest one that covers what you enable in `config.toml`.

| Tag | Extras included |
| --- | --- |
| `reluce/szurubooru-toolkit:latest` | none (slim, default) |
| `reluce/szurubooru-toolkit:latest-wd-tagger` | WD tagger (ONNX Runtime + ffmpeg) |
| `reluce/szurubooru-toolkit:latest-wd-tagger-cuda` | WD tagger with CUDA acceleration (large image) |
| `reluce/szurubooru-toolkit:latest-pixiv` | Pixiv metadata support |
| `reluce/szurubooru-toolkit:latest-all` | WD tagger (CPU) + Pixiv |

Published images target Linux on AMD64. Use a release tag such as
`2.1.1-wd-tagger` to keep scheduled jobs on a specific toolkit version.
Features added after a release require a newer image or a source build.
To build from a checkout with CPU tagging, run the following command in the
repository root and use `szuru-toolkit:local` in Compose.

```sh
docker build --build-arg 'EXTRAS=--extra wd-tagger' -t szuru-toolkit:local .
```

## NVIDIA acceleration

The `-wd-tagger-cuda` image needs an NVIDIA GPU exposed to the container. Install
the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
on the host (driver 580+ / CUDA 13), use the `latest-wd-tagger-cuda` image, and
uncomment the `deploy.resources.reservations.devices` block in `docker-compose.yml`.
Set `wd_tagger = true` and `wd_tagger_providers = ["CUDAExecutionProvider"]` under
`[auto_tagger]` in `config.toml`.

Choose one device configuration. The supplied reservation follows Docker's
[GPU access example](https://docs.docker.com/compose/how-tos/gpu-support/).
Compose 2.30.0 or newer also supports
[`gpus: all`](https://docs.docker.com/reference/compose-file/services/#gpus).

Check your Compose version and device access before starting.

```sh
docker compose version
docker compose config --quiet
docker compose run --rm --entrypoint nvidia-smi szurubooru-toolkit
```

`nvidia-smi` should list the host GPU inside the container. Check the toolkit's
DEBUG file log for the providers selected when the WD model loads.

## Set up Compose

1. Copy [docker-compose.yml](../docker-compose.yml) to a deployment directory
   and select the image tag you want to run.

1. Copy [config_sample.toml](../config_sample.toml) to `config.toml` in the
   deployment directory. Set your [board credentials](setup.md#connect-to-szurubooru).

1. Copy [crontab_sample](../crontab_sample) to `crontab`. Replace the example
   with the jobs you want to schedule. Use an empty `crontab` for manual runs.

1. Make sure to set the `src_path` option in `config.toml` to use
   `/szurubooru-toolkit/upload_src`. If you're using a different directory than
   `upload_src`, you may need to update the `docker-compose.yml` binding to be
   something like `./uploads:/szurubooru-toolkit/uploads`, and set
   `/szurubooru-toolkit/uploads` as the `src_path` option instead.

1. Create the `misc`, `tmp` and `upload_src` directories in the same location.

   For [recurring single-feed imports](importing.md#recurring-imports-from-one-feed), a
   `queue_path` such as `/szurubooru-toolkit/tmp/x-likes` uses the existing
   `./tmp` bind mount. The cron user needs write access to that directory.

   To read [tag files](tagging.md#create-tags) from the host, put them in
   `misc/tags` and use their container paths with `--tag-file`.

1. Run `touch szurubooru_toolkit.log` in the same location to create a file for
   the log. You may need to set the log location to
   `/szurubooru-toolkit/szurubooru_toolkit.log` in `config.toml`.

1. Start the service and check its startup output.

   ```sh
   docker compose up -d
   docker compose logs -f szurubooru-toolkit
   ```

You can run an individual command inside the running service.

```sh
docker compose exec szurubooru-toolkit uv run szuru-toolkit find-duplicates --limit 20 --no-set-relations "date:today"
```

For a container that runs one command and exits, set the service's
`command` to the toolkit invocation. Paths in `config.toml` and command
arguments must be visible from inside the container. For example, bind-mount
cookie files or a local [WD model directory](tagging.md#wd-tagger) if used.
To retain downloaded WD models when replacing a container, persist its
Hugging Face cache or bind-mount a local model.

## Schedule jobs

Use standard cron syntax in `crontab`. Use a lock to prevent overlapping
runs when the same job can take longer than its interval. For example, with
`queue_path = "/szurubooru-toolkit/tmp/x-likes"` in a dedicated job's
configuration and a cookie path set in that configuration, this job checks
one X feed every 15 minutes.

```cron
*/15 * * * * cd /szurubooru-toolkit && /usr/bin/flock -n /szurubooru-toolkit/tmp/x-likes.lock /usr/local/bin/uv run szuru-toolkit --hide-progress import-from-url --range 1-50 --workers 1 "https://x.com/USERNAME/likes" >/proc/1/fd/1 2>&1
```

The redirection sends command output to the container log. After changing
the crontab, restart the service to install the updated schedule.

Set `PUID` and `PGID` in [docker-compose.yml](../docker-compose.yml) if cron jobs
need the UID and group of a non-root user. The entrypoint creates or reuses the
matching account, adjusts ownership in the toolkit directory and leaves the
upload source mount alone. It redirects the documented `/proc/1/fd/1` cron
output to an internal log file that the cron user can write, then streams it
to container output. Ensure the user can read its configuration and cookies
and write its working directories.
