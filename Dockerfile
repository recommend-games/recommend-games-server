FROM gcr.io/google-appengine/python:2022-01-07-133539

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.

RUN mkdir -p /app
WORKDIR /app

RUN python3.7 -m pip install --no-cache-dir --upgrade \
        gsutil==5.15 \
        pipenv==2022.10.25
COPY Pipfile* ./
RUN pipenv install --deploy --verbose

COPY VERSION .boto gs.json startup.sh ./
COPY rg rg
COPY games games
COPY static static

ENTRYPOINT ["pipenv", "run", "/bin/bash", "startup.sh"]
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "16", "rg.wsgi:application"]
