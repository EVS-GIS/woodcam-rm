FROM python:3.9
WORKDIR /app

COPY . .

RUN pip install -e .
RUN pip install gunicorn

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "woodcamrm:create_app()"]