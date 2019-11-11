FROM gcr.io/google-appengine/python:2019-10-29-112446

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV MAILTO=''
ENV PYTHONPATH=.

RUN mkdir -p /app
WORKDIR /app

RUN pip3 install --upgrade \
        gsutil==4.46 \
        pipenv==2018.11.26
COPY Pipfile* ./
RUN pipenv install --deploy --verbose

COPY .boto gs.json startup.sh ./
COPY ludoj ludoj
COPY games games
COPY static static

ENTRYPOINT ["pipenv", "run", "/bin/bash", "startup.sh"]
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "16", "ludoj.wsgi:application"]
