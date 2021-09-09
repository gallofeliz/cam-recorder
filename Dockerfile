FROM python:3.8-alpine3.12

RUN pip install python-json-logger requests \
    && apk add --update --no-cache --virtual .tmp gcc libc-dev linux-headers git \
    && apk add --no-cache jpeg-dev zlib-dev tzdata \
    && pip install Pillow \
    && pip install git+https://github.com/gallofeliz/python-gallocloud-utils \
    && apk del .tmp \
    && mkdir /data \
    && chown nobody:nobody /data

WORKDIR /app

ADD app.py .

VOLUME /data

USER nobody

CMD python -u ./app.py
