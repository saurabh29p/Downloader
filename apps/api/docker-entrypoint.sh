#!/bin/sh
# Start as root only long enough to match the host user's ids (PUID/PGID) and
# make the data and downloads folders writable, then run the app as that user.
set -eu

if [ "$(id -u)" = "0" ]; then
  PUID="${PUID:-1000}"
  PGID="${PGID:-1000}"
  groupmod -o -g "$PGID" anyget
  usermod -o -u "$PUID" anyget
  for dir in "$ANYGET_DATA_DIR" "$ANYGET_DOWNLOADS_DIR"; do
    mkdir -p "$dir"
    chown "$PUID:$PGID" "$dir"
  done
  exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups "$@"
fi

exec "$@"
