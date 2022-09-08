FROM python:3.9-alpine3.16

COPY . .

RUN apt-get -y update && apt-get -y install ffmpeg
RUN pip install ffmpeg-python

RUN crontab crontab

CMD ["crond", "-f"]