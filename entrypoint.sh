#!/usr/bin/env sh

chown root /etc/cron.d/crontab
chmod 644 /etc/cron.d/crontab
crontab /etc/cron.d/crontab
cron -f
