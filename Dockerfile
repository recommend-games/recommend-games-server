FROM gcr.io/google-appengine/python:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.

RUN mkdir -p /app
WORKDIR /app

RUN apt-get -y update && \
    apt-get -y install --no-install-recommends \
        git \
        libatlas3-base && \
    apt-get -y autoremove && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip2 install --upgrade gsutil && \
    pip3 install --upgrade pip pipenv
COPY Pipfile* ./
RUN pipenv install --deploy

COPY .boto gs.json startup.sh ./
COPY ludoj ludoj
COPY games games

ENTRYPOINT ["pipenv", "run", "/bin/bash", "startup.sh"]
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "16", "ludoj.wsgi:application"]
