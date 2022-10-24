FROM python:3.9

COPY archive_compression.py archive_compression.py
COPY crontab /etc/cron.d/crontab

RUN apt-get update -y && apt-get install -y cron ffmpeg
RUN pip install numpy requests python-dotenv ffmpeg-python
RUN touch /var/log/archivecompression.log

RUN crontab /etc/cron.d/crontab

CMD cron && tail -f /var/log/archivecompression.log