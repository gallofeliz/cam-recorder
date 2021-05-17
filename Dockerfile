FROM python:3.8-alpine3.12

RUN pip install python-json-logger requests

RUN apk add --update --no-cache --virtual .tmp gcc libc-dev linux-headers \
    && apk add --no-cache jpeg-dev zlib-dev \
    && pip install Pillow \
    && apk del .tmp

RUN apk add --update --no-cache --virtual .tmp git \
    && echo 1 \
    && pip install git+https://github.com/gallofeliz/python-gallocloud-utils \
    && apk del .tmp

WORKDIR /app

ADD app.py .

CMD python -u ./app.py
