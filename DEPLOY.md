# Deployment to Google Cloud

## Create Google Cloud project

Log in to [Google Cloud console](https://console.cloud.google.com) and create a
new project. We'll refer to the project ID you chose as `$PROJECT`.

Run `gcloud init` to initialise your project in your terminal.

## Create App Engine app

Open the [App Engine dashboard](https://console.cloud.google.com/appengine) and
create a new app in the region of your choice with the flexible environment.

## Create Storage buckets

Open the [Storage dashboard](https://console.cloud.google.com/storage) and
create the bucket `$PROJECT-data` in the same region as the App Engine app
above. Leave the default options otherwise.

## Create PubSub topic and subscription

Open the [PubSub dashboard](https://console.cloud.google.com/cloudpubsub) and
create the topic `users`, then a subscription `crawl` attached to that topic.
Set this subscription to "Pull" delivery type, "Never expire", 600 seconds
acknowledgement deadline, and 1 day retention duration.

## Quick summary

* Create GC project
* Create GAE app (default)
* Create GCS bucket
* Create PubSub topic and subscription
* Activate GCR
* Create credentials for default service account and download as `gs.json`
* Login to docker: `cat gs.json | docker login -u _json_key --password-stdin https://gcr.io` (https://cloud.google.com/container-registry/docs/advanced-authentication#json_key_file)
* Login to Gcloud: `gcloud auth login` (might need `export CLOUDSDK_PYTHON=python3`)
* Change settings (project, bucket, queue, etc): `.env` and `app.yaml`
* Make sure domain `.${project}.appspot.com` is whitelisted in `settings.py` under `ALLOWED_HOSTS`
* Configure domains, if any