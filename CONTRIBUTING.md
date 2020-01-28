# Contribution guidelines

This document describes how to get started with development and how you can
contribute to this project.

## Getting started

In order to get your environment set up, first make sure you have
[Pipenv](https://pipenv.readthedocs.io/) installed. Then install and activate
the environment via

```bash
pipenv install --dev
pipenv shell
```

Check if Django is installed and has no issues:

```bash
./manage.py check
```

In order to build the full environment, you'll need to install the following tools:

* [Git](https://git-scm.com/)
* [Docker](https://www.docker.com/)
* [SQLite](https://www.sqlite.org)
* [Google Cloud SDK](https://cloud.google.com/sdk/)
* [ShellCheck](https://github.com/koalaman/shellcheck)
* [Hadolint](https://github.com/hadolint/hadolint)
* [MarkdownLint](https://github.com/igorshubovych/markdownlint-cli)
* [Markdown lint](https://github.com/markdownlint/markdownlint)
* [HTMLHint](https://github.com/htmlhint/HTMLHint)
* [JSHint](https://github.com/jshint/jshint)
* [JSLint](https://github.com/reid/node-jslint)
* [CSSLint](https://github.com/CSSLint/csslint)

If you want to deploy the server to a new Google Cloud environment, read the
[deployment guidelines](DEPLOY.md).
