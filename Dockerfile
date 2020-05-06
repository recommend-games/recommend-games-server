FROM gcr.io/google-appengine/python:2020-03-29-162500

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.

RUN mkdir -p /app
WORKDIR /app

RUN python3.7 -m pip install --upgrade \
        gsutil==4.50 \
        poetry==1.0.5
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-interaction --verbose

COPY VERSION .boto gs.json startup.sh ./
COPY rg rg
COPY games games
COPY static static

ENTRYPOINT ["poetry", "run", "/bin/bash", "startup.sh"]
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "16", "rg.wsgi:application"]
