#!/usr/bin/env sh
set -e

# Run cron jobs as a custom user when PUID/PGID are set (e.g. for NFS mounts or
# rootless containers). Without them, everything runs as root as before.
CRON_USER=root

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
    chown -R "$PUID:$PGID" /szurubooru-toolkit || echo 'Warning: could not chown /szurubooru-toolkit, check your volume permissions'
fi

chown root /etc/cron.d/crontab
chmod 644 /etc/cron.d/crontab
crontab -u "$CRON_USER" /etc/cron.d/crontab
cron -f
