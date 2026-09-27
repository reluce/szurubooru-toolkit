#!/usr/bin/env sh
set -e

# Run cron jobs as a custom user when PUID/PGID are set (e.g. for NFS mounts or
# rootless containers). Without them, everything runs as root as before.
CRON_USER=root

# Never modify the bind-mounted crontab; install a copy instead.
# Cron doesn't pass the container's environment to jobs, so set UV_NO_SYNC
# (see Dockerfile) in the crontab itself; otherwise every `uv run` re-syncs.
{ echo 'UV_NO_SYNC=1'; cat /etc/cron.d/crontab; } > /tmp/crontab

if [ -n "$PUID" ] || [ -n "$PGID" ]; then
    PUID="${PUID:-1000}"
    PGID="${PGID:-1000}"

    if ! getent group "$PGID" >/dev/null; then
        groupadd --gid "$PGID" toolkit
    fi

    if ! getent passwd "$PUID" >/dev/null; then
        useradd --uid "$PUID" --gid "$PGID" --no-create-home --home-dir /szurubooru-toolkit toolkit
    fi
    CRON_USER="$(getent passwd "$PUID" | cut -d: -f1)"

    echo "Running cron jobs as $CRON_USER ($PUID:$PGID)"
    # upload_src is only ever read and is often a read-only mount; skip it.
    find /szurubooru-toolkit -path /szurubooru-toolkit/upload_src -prune -o -exec chown -h "$PUID:$PGID" {} + 2>/dev/null \
        || echo 'Warning: could not chown /szurubooru-toolkit, check your volume permissions'

    # A non-root job can't open /proc/1/fd/1 (it belongs to PID 1), so rewrite
    # the documented redirect to a log file the cron user can write, and tail
    # it to stdout for docker logs.
    # ponytail: truncated on start, no rotation — add logrotate if a container
    # runs long enough for the log to matter.
    LOG_FILE=/var/log/szuru-toolkit.log
    : > "$LOG_FILE"
    chown "$PUID:$PGID" "$LOG_FILE"
    sed -i 's|> */proc/1/fd/1 *2>&1|>> '"$LOG_FILE"' 2>\&1|g' /tmp/crontab

    tail -F "$LOG_FILE" &
fi

chown root /tmp/crontab
chmod 644 /tmp/crontab
crontab -u "$CRON_USER" /tmp/crontab
exec cron -f
