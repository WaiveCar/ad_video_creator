## Before first run...

        mkdir output

## Running within Docker:

        docker build -t ad_video_creator .
        docker run --volume $(pwd)/output:/app/output ad_video_creator http://9ol.es/flipper.php

## Running locally

Start Chromium in headless mode with Remote Debugging

        # Locally
        chromium --remote-debugging-port=9222 --headless
        # OR in a Docker container
        docker run -d -p 9222:9222 --rm --name headless-shell chromedp/headless-shell

        python3 ./create_ad_video.py http://9ol.es/flipper.php

