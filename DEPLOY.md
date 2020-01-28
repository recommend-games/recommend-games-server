# Deployment to Google Cloud

This document describes the deployment process to a new Google Cloud environment.
If you just want to learn how to get started or what tools you need to install,
read the [contribution guidelines](CONTRIBUTING.md).

## Create Google Cloud project

Log in to [Google Cloud console](https://console.cloud.google.com) and create a
new project. We'll refer to the project ID you chose as `$PROJECT`.

You may have to activate billing and upgrade your account to access all features
required for this project.

Run `gcloud init` to initialise your project in your terminal, then authenticate
via `gcloud auth login`. In case you're having trouble with Python 2 vs 3, try:

```bash
CLOUDSDK_PYTHON=python3 gcloud auth login
```

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

Also make sure to update the PubSub project, topic, and subscription in the
[scraper](https://gitlab.com/recommend.games/board-game-scraper/blob/master/.env.example).

## Create credentials for default service account

Go to the [IAM & admin dashboard](https://console.cloud.google.com/iam-admin),
section [Service accounts](https://console.cloud.google.com/iam-admin/serviceaccounts),
and find the App Engine default service account. Select "Create key" from the
actions, and download the key in JSON format. Move that file to the root of this
project as `gs.json`. **This is a private key, do not check it into version
control!**

Now you should be able to log in to [Container Registry](https://console.cloud.google.com/gcr):

```bash
cat gs.json | docker login -u _json_key --password-stdin https://gcr.io
```

Read more about using [JSON credentials to access GCR](https://cloud.google.com/container-registry/docs/advanced-authentication#json_key_file).

## Update settings

Edit your [`.env`](.env.example) file to use the correct project:

```bash
GC_PROJECT=$PROJECT
```

Similarly, edit [`app.yaml`](app.yaml) to use the correct environment variables:

```yaml
env_variables:
    GC_PROJECT: $PROJECT
    GC_DATA_BUCKET: $PROJECT-data
    PUBSUB_QUEUE_PROJECT: $PROJECT
    PUBSUB_QUEUE_TOPIC: users
```

The App Engine domain should be automatically added to `ALLOWED_HOSTS` in
[settings.py](rg/settings.py) if `$GC_PROJECT` is configured correctly.
Should you experience problems with your domain not being whitelisted, check
there first.

## Deploy

You should now be able to deploy the service. For a full release, simply run

```bash
./release.sh
```

If you don't need to build a new recommender and datebase version, it should
suffice to run

```bash
pipenv run pynt syncdata releaseserver
```

Either way, after successful deployment the service should be available at
[https://$PROJECT.appspot.com/](https://this-could-be-your-project.appspot.com/).

## Configure domains

If you're using custom domains, navigate to the
[corresponding settings](https://console.cloud.google.com/appengine/settings/domains)
and follow the instructions. If the domain was previously used in a different
project, you will need to unassign it first.

## Enjoy!

Everything should be done! Sit back and relax...
