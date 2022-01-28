FROM python:alpine
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY . ./

CMD gunicorn -b 0.0.0.0:80 app.app:server