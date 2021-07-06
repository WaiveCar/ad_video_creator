#!/usr/bin/env bash

if [ -z ${1} ]; then
  exit "You must pass the URL you'd like a video of as an argument."
fi

nohup /headless-shell/headless-shell --no-sandbox --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 &

python3 -i ./create_ad_video.py "127.0.0.1:9222" "${1}"
