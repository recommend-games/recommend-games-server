# Deployment

The service is deployed as a Docker image to the
[Heroku container registry](https://devcenter.heroku.com/articles/container-registry-and-runtime).

There are two independent release paths:

1. **Data + static API** — rebuilds the SQLite database and publishes a static
   API to the sibling `recommend-games-api` repository.
2. **Server image** — builds and releases the Docker image that serves the API.

## Prerequisites

* [uv](https://docs.astral.sh/uv/) and the project environment (`uv sync`)
* [Docker](https://www.docker.com/)
* [SQLite](https://www.sqlite.org)
* The [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli), logged in
  via `heroku login`
* These sibling checkouts next to this repository:
  * `board-game-data` — scraped data and rankings
  * `board-game-scraper` — scraper feeds
  * `board-game-recommender` — where the trained model is written
  * `recommend-games-config` — premium user config
  * `recommend-games-api` — target for the static API

Set `HEROKU_APP` in `.env` (see [`.env.example`](.env.example)) if the app is
not named `recommend-games`.

Training the recommender needs PyTorch, which has no macOS x86_64 wheels — a
full release therefore requires Linux or Apple Silicon.

## Releasing data

```bash
./release.sh
```

This runs the full task chain through invoke — merging scraped files, training
the recommender, snapshotting the R.G rankings, rebuilding the database,
scoring Kennerspiel, generating the sitemap — and then publishes the static API
and pushes it.

To inspect what a release would do without touching anything:

```bash
uv run invoke -c build --dry builddbfull
```

## Releasing the server

```bash
uv run invoke -c build release       # rebuild the database, then deploy
uv run invoke -c build releasefull   # also re-merge and retrain first
```

Both end in `releaseserver`, which builds the image, tags the commit with the
contents of [`VERSION`](VERSION), pushes to `registry.heroku.com` and calls
`heroku container:release`.

To build and run the image locally instead:

```bash
docker compose up --build
```

The image contains only the runtime dependencies plus `rg/`, `games/`,
`static/` and `data/`. Everything that builds data — PyTorch, pandas,
scikit-learn, invoke — stays on the developer machine.

Note that `static/` and `data/` are build artifacts and are not in Git; run
`uv run invoke -c build collectstatic` and the data pipeline before building
the image.
