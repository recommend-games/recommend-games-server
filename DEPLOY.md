# Deployment

The service is deployed as a Docker image to the
[Heroku container registry](https://devcenter.heroku.com/articles/container-registry-and-runtime).

There are two release paths:

1. **Full end-to-end release** — merges scraped data, trains the recommender, rebuilds the SQLite database, and builds and deploys the server Docker image.
2. **Database-only rebuild** — rebuilds the database from existing scraped data and trained models without deploying.

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

Set `HEROKU_APP` in `.env` (see [`.env.example`](.env.example)) if the app is
not named `recommend-games`.

Training the recommender needs PyTorch, which has no macOS x86_64 wheels — a
full release therefore requires Linux or Apple Silicon.

## Full release

```bash
./release.sh
```

This runs `uv run invoke -c build releasefull` — merging scraped files, training
the recommender, snapshotting the R.G rankings, rebuilding rankings and charts,
rebuilding the database, scoring Kennerspiel, generating the sitemap, committing data
updates, and building/releasing the Docker image to Heroku.

To inspect what a release would do without touching anything:

```bash
uv run invoke -c build --dry releasefull
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
