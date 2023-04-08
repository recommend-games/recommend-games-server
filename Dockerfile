FROM python:3.7.16-alpine

ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.

RUN mkdir -p /app
WORKDIR /app

RUN apk add --no-cache g++=12.2.1_git20220924-r4 \
    && rm -rf /var/cache/apk/* \
    && python3.7 -m pip install --no-cache-dir --upgrade pipenv==2023.3.20
COPY Pipfile* ./
RUN pipenv install --system --deploy --verbose

COPY VERSION VERSION
COPY rg rg
COPY games games
COPY static static
COPY data data

RUN adduser -D gamer
USER gamer

CMD gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 8 \
    rg.wsgi:application
