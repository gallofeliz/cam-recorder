FROM python:alpine

RUN pip install python-json-logger requests

WORKDIR /app

ADD app.py .

CMD python -u ./app.py
