FROM gcr.io/google-appengine/python:2019-09-10-092415

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.

RUN mkdir -p /app
WORKDIR /app

RUN apt-get -y update && \
    apt-get -y install --no-install-recommends \
        git=1:2.7.4-0ubuntu1.6 \
        libatlas3-base=3.10.2-9 && \
    apt-get -y autoremove && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install --upgrade \
        gsutil==4.42 \
        pipenv==2018.11.26
COPY Pipfile* ./
RUN pipenv install --deploy

COPY .boto gs.json startup.sh ./
COPY ludoj ludoj
COPY games games
COPY static static

ENTRYPOINT ["pipenv", "run", "/bin/bash", "startup.sh"]
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "16", "ludoj.wsgi:application"]
