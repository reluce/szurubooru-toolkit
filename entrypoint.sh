#!/usr/bin/env sh

# add aliases
alias auto-tagger="poetry run auto-tagger"
alias create-tags="poetry run create-tags"
alias delete-posts="poetry run delete-posts"
alias import-from-booru="poetry run import-from-booru"
alias reset-posts="poetry run reset-posts"
alias upload-media="poetry run upload-media"
alias tag-posts="poetry run tag-posts"

# setup crontab
chown root /etc/cron.d/crontab
chmod 644 /etc/cron.d/crontab
crontab /etc/cron.d/crontab
cron -f
