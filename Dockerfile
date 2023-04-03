FROM python:3.7.16
# TODO get rid of Git dependency and use alpine

ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.

RUN mkdir -p /app
WORKDIR /app

RUN python3.7 -m pip install --no-cache-dir --upgrade \
    pipenv==2023.3.20
COPY Pipfile* ./
RUN pipenv install --system --deploy --verbose

COPY rg rg
COPY games games
COPY static static
COPY data data

RUN useradd -m gamer
USER gamer

CMD gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 16 \
    rg.wsgi:application
