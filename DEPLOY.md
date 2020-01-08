# Deployment to Google Cloud

Some of the steps required:
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