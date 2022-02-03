FROM python:alpine
COPY . ./
RUN pip install -e .

CMD gunicorn -b 0.0.0.0:80 app.app:server