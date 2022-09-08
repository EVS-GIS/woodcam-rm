FROM python:3.9
WORKDIR /app

COPY . .

RUN apt-get -y update && apt-get -y install python3-opencv && apt-get clean
ENV PYTHONPATH "${PYTHONPATH}:/usr/lib/python3/dist-packages"

RUN pip install -e .
RUN pip install gunicorn

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "woodcamrm:create_app()"]