FROM python:alpine

RUN pip install python-json-logger requests

RUN apk add --update --no-cache --virtual .tmp gcc libc-dev linux-headers \
    && apk add --no-cache jpeg-dev zlib-dev \
    && pip install Pillow \
    && apk del .tmp

WORKDIR /app

ADD app.py .

CMD python -u ./app.py
