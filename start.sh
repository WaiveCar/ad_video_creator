#!/usr/bin/env bash

nohup /headless-shell/headless-shell --no-sandbox --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 &

python3 ./create_ad_video.py ${@}
