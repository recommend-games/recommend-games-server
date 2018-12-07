# ludoj-server #

Board game recommendation service. Live demo: https://recommend.games/

## Quick start ##

```bash
docker-compose up
```

This will build the docker image (only on first start) and run the server. You should be able to access the service at http://localhost:8000/.

However, in order to access useful data, you need to fill the SQLite database first. See `release.sh` for the steps to build a full release.

## Recommendation engine ##

Personal recommendations are based on data from [BoardGameGeek](https://boardgamegeek.com/) and computed by our [recommendation engine](https://gitlab.com/mshepherd/ludoj-recommender).
