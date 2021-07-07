FROM chromedp/headless-shell:latest

WORKDIR /app

RUN apt update && \
    apt install -y python3-pip ffmpeg

COPY ./requirements.txt ./

RUN pip3 install -r requirements.txt

COPY ./create_ad_video.py ./start.sh ./

VOLUME /app/output

ENTRYPOINT ["./start.sh"]
