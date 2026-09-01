# Contribution guidelines

This document describes how to get started with development and how you can
contribute to this project.

## Getting started

Make sure you have [uv](https://docs.astral.sh/uv/) installed, then set up the
environment:

```bash
uv sync
```

That installs Python 3.14 (per `.python-version`), the runtime dependencies and
the `build` and `dev` dependency groups.

Check if Django is installed and has no issues:

```bash
uv run ./manage.py check
```

Run the app against an existing database:

```bash
uv run ./manage.py runserver
```

### A note on architecture

The `build` group installs [PyTorch](https://pytorch.org/), which publishes no
macOS x86_64 wheels. On an Intel Mac `uv sync` will fail trying to build torch
from source. You can still work on everything the server itself does with:

```bash
uv sync --no-default-groups
```

Training the recommender and building the database require Linux or Apple
Silicon.

## Build tasks

Build orchestration lives in [`build.py`](build.py) and runs through
[invoke](https://www.pyinvoke.org/):

```bash
uv run invoke -c build --list          # show all tasks
uv run invoke -c build builddb         # build a new database
uv run invoke -c build --dry release   # show what a release would do
```

See [`release.sh`](release.sh) for the full release pipeline.

## Linting and formatting

[ruff](https://docs.astral.sh/ruff/) handles linting and formatting, wired up
through pre-commit:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

The `lint` task additionally runs the non-Python linters, which you need to
install separately:

* [Git](https://git-scm.com/)
* [Docker](https://www.docker.com/)
* [SQLite](https://www.sqlite.org)
* [ShellCheck](https://github.com/koalaman/shellcheck)
* [Hadolint](https://github.com/hadolint/hadolint)
* [MarkdownLint](https://github.com/igorshubovych/markdownlint-cli)
* [Markdown lint](https://github.com/markdownlint/markdownlint)
* [HTMLHint](https://github.com/htmlhint/HTMLHint)
* [JSHint](https://github.com/jshint/jshint)
* [JSLint](https://github.com/reid/node-jslint)
* [CSSLint](https://github.com/CSSLint/csslint)

Read the [deployment guidelines](DEPLOY.md) for how a release reaches
production.
