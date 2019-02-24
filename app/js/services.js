/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $, moment */

'use strict';

ludojApp.factory('gamesService', function gamesService(
    $document,
    $log,
    $http,
    $q,
    $sessionStorage,
    $window,
    API_URL,
    APP_TITLE,
    CANONICAL_URL,
    DEFAULT_IMAGE,
    GA_TRACKING_ID,
    SITE_DESCRIPTION
) {
    var service = {},
        cache = {},
        linkedSites = ['bgg', 'bga', 'wikidata', 'wikipedia', 'luding', 'spielen'];

    function putCache(game, id) {
        if (_.isEmpty(game)) {
            return;
        }
        id = id || game.bgg_id;
        if (id) {
            cache[id] = game;
        }
    }

    function getCache(id) {
        var game = cache[id];
        return !_.isEmpty(game) ? game : null;
    }

    service.allGames = function allGames() {
        return _.values(cache);
    };

    function join(array, sep, lastSep) {
        sep = sep || ', ';

        if (!lastSep || _.size(array) <= 1) {
            return _.join(array, sep);
        }

        return _.join(_.slice(array, 0, -1), sep) + lastSep + _.last(array);
    }

    function between(lower, value, upper) {
        lower = parseFloat(lower);
        value = parseFloat(value);
        upper = parseFloat(upper);
        return _.isNaN(lower) || _.isNaN(value) || _.isNaN(upper) ? false : lower <= value && value <= upper;
    }

    function starClasses(score) {
        if (!between(1, score, 5)) {
            return [];
        }

        return _.map(_.range(1, 6), function (star) {
            return score >= star ? 'fas fa-star'
                : score >= star - 0.5 ? 'fas fa-star-half-alt' : 'far fa-star';
        });
    }

    function externalLink(site, id) {
        site = _.head(_.split(site, '_', 1));

        if (!site || !id) {
            return null;
        }

        var result = {'site': site};

        if (site === 'bgg') {
            result.url = 'https://boardgamegeek.com/boardgame/' + id + '/';
            result.label = 'BoardGameGeek';
            result.icon_url = '/assets/bgg-color.svg';
        } else if (site === 'bga') {
            result.url = 'https://www.boardgameatlas.com/search/game/' + id + '?amazonTag=ludoj0f-20';
            result.label = 'Board Game Atlas';
            result.icon_url = '/assets/bga.png';
        } else if (site === 'wikidata') {
            result.url = 'https://www.wikidata.org/wiki/' + id;
            result.label = 'Wikidata';
            result.icon_url = '/assets/wikidata.svg';
        } else if (site === 'wikipedia') {
            result.url = 'https://en.wikipedia.org/wiki/' + id;
            result.label = 'Wikipedia';
            result.icon_class = 'fab fa-wikipedia-w';
        } else if (site === 'luding') {
            result.url = 'http://www.luding.org/cgi-bin/GameData.py/ENgameid/' + id;
            result.label = 'Luding';
        } else if (site === 'spielen') {
            result.url = 'https://gesellschaftsspiele.spielen.de/alle-brettspiele/' + id + '/';
            result.label = 'spielen.de';
            result.icon_url = '/assets/spielen.png';
        } else {
            return null;
        }

        return result;
    }

    function processGame(game) {
        game.name_short = _.size(game.name) > 50 ? _.truncate(game.name, {'length': 50, 'separator': /,? +/}) : null;
        game.name_url = encodeURIComponent(_.toLower(game.name));
        game.alt_name = game.name_short ? _.uniq(_.concat(game.name, game.alt_name)) : _.without(game.alt_name, game.name);

        // filter out '(Uncredited)' / #3
        game.designer = _.without(game.designer, 3);
        game.designer_name = _.without(game.designer_name, '(Uncredited)');
        game.artist = _.without(game.artist, 3);
        game.artist_name = _.without(game.artist_name, '(Uncredited)');

        game.designer_display = join(game.designer_name, ', ', ' & ');
        game.artist_display = join(game.artist_name, ', ', ' & ');
        game.description_array = _.filter(_.map(_.split(game.description, /\n(\s*\n\s*)+/), _.trim));
        game.description_short = _.size(game.description) > 250 ? _.truncate(game.description, {'length': 250, 'separator': /,? +/}) : null;

        game.designer_data = _.isEmpty(game.designer) || _.isEmpty(game.designer_name) ?
                null : _.fromPairs(_.zip(game.designer, game.designer_name));
        game.artist_data = _.isEmpty(game.artist) || _.isEmpty(game.artist_name) ?
                null : _.fromPairs(_.zip(game.artist, game.artist_name));

        var counts = _.map(_.range(1, 11), function (count) {
                return between(game.min_players_best, count, game.max_players_best) ? 3
                        : between(game.min_players_rec, count, game.max_players_rec) ? 2
                        : between(game.min_players, count, game.max_players) ? 1 : 0;
            }),
            styles = ['not', 'box', 'recommended', 'best'],
            alts = [
                'not playable with',
                'playable with',
                'recommended for',
                'best with'
            ],
            times = _([game.min_time, game.max_time])
                .filter()
                .sortBy()
                .uniq()
                .join('–'),
            complexities = [
                null,
                'light',
                'medium light',
                'medium',
                'medium heavy',
                'heavy'
            ],
            language_dependencies = [
                null,
                'no necessary in-game text',
                'some necessary text',
                'moderate in-game text',
                'extensive use of text',
                'unplayable in another language'
            ],
            externalLinks = _.flatMap(linkedSites, function (site) {
                return _([game[site + '_id']])
                    .flatten()
                    .filter()
                    .map(function (id) {
                        return externalLink(site, id);
                    })
                    .filter()
                    .value();
            });

        game.counts = _.map(counts, function (rec, count) {
            count += 1;
            var string = _.padStart(count, 2, '0'),
                image = rec === 0 ? 'meeple_' + string + '_empty.svg' : 'meeple_' + string + '.svg',
                style = 'player-count-' + styles[rec],
                alt = alts[rec] + ' ' + count + ' player' + (count > 1 ? 's' : '');
            return {
                'count': count,
                'rec': rec,
                'style': style,
                'image': '/assets/meeples/' + image,
                'alt': alt
            };
        });

        game.time_string = times ? times + ' minutes' : null;
        game.complexity_string = between(1, game.complexity, 5) ?
                complexities[_.round(game.complexity)] + ' complexity' : null;
        game.language_dependency_string = between(1, game.language_dependency, 5) ?
                language_dependencies[_.round(game.language_dependency)] : null;
        game.cooperative_string = game.cooperative === true ? 'cooperative' : game.cooperative === false ? 'competitive' : null;
        game.star_classes = starClasses(game.rec_stars);
        game.external_links = _.isEmpty(externalLinks) ? null : externalLinks;

        return game;
    }

    function getGames(page, filters, noblock) {
        var url = API_URL + 'games/',
            params = _.isEmpty(filters) ? {} : _.cloneDeep(filters);
        page = page || null;

        if (page) {
            params.page = page;
        }

        if (params.user || !_.isEmpty(params.like)) {
            url += 'recommend/';
        }

        $log.debug('query parameters', params);

        return $http.get(url, {'params': params, 'noblock': !!noblock})
            .then(function (response) {
                var games = _.get(response, 'data.results');

                if (!games) {
                    return $q.reject('Unable to load games.');
                }

                games = _.map(games, processGame);
                response.data.results = games;
                response.data.page = page;

                if (!params.user && _.isEmpty(params.like)) {
                    _.forEach(games, function (game) {
                        putCache(game);
                    });
                }

                return response.data;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load games.';
                return $q.reject({
                    'reason': response,
                    'status': _.get(reason, 'status')
                });
            });
    }

    service.getGames = getGames;

    service.getGame = function getGame(id, forceRefresh, noblock) {
        id = _.parseInt(id);
        var cached = forceRefresh ? null : getCache(id);

        if (!_.isEmpty(cached)) {
            return $q.resolve(cached);
        }

        return $http.get(API_URL + 'games/' + id + '/', {'noblock': !!noblock})
            .then(function (response) {
                var responseId = _.get(response, 'data.bgg_id'),
                    game;

                if (id !== responseId) {
                    return $q.reject('Unable to load game.');
                }

                game = processGame(response.data);
                putCache(game, id);
                return game;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load game.';
                return $q.reject(response);
            });
    };

    service.getCachedGames = function getCachedGames() {
        return $sessionStorage.games || {};
    };

    service.setCachedGames = function setCachedGames(games) {
        $sessionStorage.games = games;
    };

    service.getPopularGames = function getPopularGames(start, end, noblock) {
        start = _.isNumber(start) ? start : 0;
        end = _.isNumber(end) ? end : 11;

        if (end <= _.size($sessionStorage.popularGames)) {
            return $q.resolve(_.slice($sessionStorage.popularGames, start, end));
        }

        function fetchGames(page) {
            return getGames(page, {
                'ordering': '-num_votes',
                'compilation': 'False'
            }, !!noblock)
                .then(function (response) {
                    var games = _.get(response, 'results');

                    $sessionStorage.popularGames = page === 1 || _.isEmpty($sessionStorage.popularGames) ? games
                        : _.concat($sessionStorage.popularGames, games);
                    $sessionStorage.popularGamesPage = page + 1;

                    if (end <= _.size($sessionStorage.popularGames)) {
                        return $q.resolve(_.slice($sessionStorage.popularGames, start, end));
                    }

                    return fetchGames(page + 1);
                });
        }

        return fetchGames($sessionStorage.popularGamesPage || 1);
    };

    service.getSimilarGames = function getSimilarGames(gameId, page, noblock) {
        page = page || null;
        var url = API_URL + 'games/' + gameId + '/similar/',
            params = page ? {'page': page} : null;

        return $http.get(url, {'params': params, 'noblock': !!noblock})
            .then(function (response) {
                var games = _.get(response, 'data.results');

                if (!games) {
                    return $q.reject('Unable to load games.');
                }

                games = _.map(games, processGame);
                response.data.results = games;
                response.data.page = page;

                if (!params.user) {
                    _.forEach(games, function (game) {
                        putCache(game);
                    });
                }

                return response.data;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load games.';
                return $q.reject({
                    'reason': response,
                    'status': _.get(reason, 'status')
                });
            });
    };

    service.getModelUpdatedAt = function getModelUpdatedAt(noblock) {
        if (!_.isEmpty($sessionStorage.model_updated_at)) {
            return $q.resolve($sessionStorage.model_updated_at);
        }

        return $http.get(API_URL + 'games/updated_at/', {'noblock': !!noblock})
            .then(function (response) {
                var updatedAt = moment(_.get(response, 'data.updated_at')),
                    updatedAtStr;
                if (!updatedAt.isValid()) {
                    return $q.reject('Unable to retrieve last update.');
                }
                updatedAtStr = updatedAt.calendar();
                $sessionStorage.model_updated_at = updatedAtStr;
                return updatedAtStr;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to retrieve last update.';
                return $q.reject(response);
            });
    };

    function processStats(stats) {
        var updatedAt = moment(stats.updated_at);
        if (updatedAt.isValid()) {
            stats.updated_at_str = updatedAt.calendar();
        } else {
            stats.updated_at = null;
            stats.updated_at_str = null;
        }
        return stats;
    }

    service.getGamesStats = function getGamesStats(noblock) {
        if (!_.isEmpty($sessionStorage.games_stats)) {
            return $q.resolve($sessionStorage.games_stats);
        }

        return $http.get(API_URL + 'games/stats/', {'noblock': !!noblock})
            .then(function (response) {
                var stats = response.data;
                if (_.isEmpty(stats)) {
                    return $q.reject('Unable to load games stats.');
                }
                stats = processStats(stats);
                $sessionStorage.games_stats = stats;
                return stats;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load games stats.';
                return $q.reject(response);
            });
    };

    service.jsonLD = function jsonLD(game) {
        if (_.isArray(game)) {
            return {
                '@context': 'http://schema.org',
                '@type': 'ItemList',
                'itemListElement': _.map(game, function (g, i) {
                    return {
                        '@type': 'ListItem',
                        'position': i + 1,
                        'url': CANONICAL_URL + '#/game/' + g.bgg_id
                    };
                })
            };
        }

        return {
            '@context': 'http://schema.org',
            '@type': 'Game',
            'name': game.name,
            'description': game.description,
            'url': CANONICAL_URL + '#/game/' + game.bgg_id,
            'image': _.head(game.image_url),
            'author': _.map(game.designer_name, function (designer) {
                return {
                    '@type': 'Person',
                    'name': designer
                };
            }),
            'datePublished': game.year,
            'audience': {
                '@type': 'PeopleAudience',
                'suggestedMinAge': game.min_age_rec || game.min_age
            },
            'typicalAgeRange': _.round(game.min_age_rec || game.min_age) + '-',
            'numberOfPlayers': {
                '@type': 'QuantitativeValue',
                'minValue': game.min_players,
                'maxValue': game.max_players
            },
            'aggregateRating': {
                '@type': 'AggregateRating',
                'ratingValue': game.bayes_rating,
                'ratingCount': game.num_votes,
                'worstRating': 1,
                'bestRating': 10
            }
            // 'timeRequired': game.max_time
            // 'publisher': game.publisher_name
        };
    };

    function canonicalPath(path, params) {
        path = '#' + (path || '/');
        var qString = _(_.toPairs(params))
                .filter(1)
                .sortBy(0)
                .map(function (v) {
                    return v[0] + '=' + encodeURIComponent(v[1]);
                })
                .join('&');
        return qString ? path + '?' + qString : path;
    }

    service.setCanonicalUrl = function setCanonicalUrl(path, params) {
        $('link[rel="canonical"]').remove();
        $('meta[property="og:url"]').remove();

        if (!path) {
            return;
        }

        path = canonicalPath(path, params);
        var url = CANONICAL_URL + path;

        $('head').append(
            '<link rel="canonical" href="' + url + '" />',
            '<meta property="og:url" content="' + url + '" />'
        );

        if (GA_TRACKING_ID && $window.gtag) {
            $window.gtag('config', GA_TRACKING_ID, {'page_path': '/' + path});
        }

        return url;
    };

    service.setTitle = function setTitle(title) {
        title = title ? title + ' – ' + APP_TITLE : APP_TITLE;

        $document[0].title = title;

        $('meta[property="og:title"]').remove();
        $('meta[name="twitter:title"]').remove();

        $('head').append(
            '<meta property="og:title" content="' + title + '" />',
            '<meta name="twitter:title" content="' + title + '" />'
        );

        return title;
    };

    service.setImage = function setImage(image) {
        image = image || (CANONICAL_URL + DEFAULT_IMAGE);

        $('meta[property="og:image"]').remove();
        $('meta[name="twitter:image"]').remove();

        $('head').append(
            '<meta property="og:image" content="' + image + '" />',
            '<meta name="twitter:image" content="' + image + '" />'
        );

        return image;
    };

    service.setDescription = function setDescription(description) {
        description = description || SITE_DESCRIPTION;

        $('meta[name="description"]').remove();
        $('meta[property="og:description"]').remove();
        $('meta[name="twitter:description"]').remove();

        $('head').append(
            '<meta name="description" content="' + description + '" />',
            '<meta property="og:description" content="' + description + '" />',
            '<meta name="twitter:description" content="' + description + '" />'
        );
    };

    return service;
});

ludojApp.factory('usersService', function usersService(
    $log,
    $http,
    $q,
    $sessionStorage,
    API_URL
) {
    var service = {};

    function processStats(stats) {
        var updatedAt = moment(stats.updated_at);
        if (updatedAt.isValid()) {
            stats.updated_at_str = updatedAt.calendar();
        } else {
            stats.updated_at = null;
            stats.updated_at_str = null;
        }
        _.forEach(['rg_top', 'bgg_top'], function (site) {
            var total = _.get(stats, site + '.total', 0);
            _.forEach(['owned', 'played', 'rated'], function (item) {
                var value = _.get(stats, site + '.' + item, 0);
                stats[site][item + '_pct'] = total ? 100 * value / total : 0;
            });
        });
        return stats;
    }

    service.getUserStats = function getUserStats(user, noblock) {
        if (!user) {
            return $q.reject('User name is required.');
        }

        user = _.toLower(user);

        if (!_.isEmpty($sessionStorage['user_stats_' + user])) {
            return $q.resolve($sessionStorage['user_stats_' + user]);
        }

        var userUri = encodeURIComponent(user);

        return $http.get(API_URL + 'users/' + userUri + '/stats/', {'noblock': !!noblock})
            .then(function (response) {
                var stats = response.data;
                if (_.isEmpty(stats)) {
                    return $q.reject('Unable to load stats for "' + user + '".');
                }
                stats = processStats(stats);
                $sessionStorage['user_stats_' + user] = stats;
                return stats;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load stats for "' + user + '".';
                return $q.reject(response);
            });
    };

    return service;
});

ludojApp.factory('newsService', function newsService(
    $http,
    $localStorage,
    $log,
    $q,
    $sessionStorage,
    API_URL
) {
    var service = {};

    $sessionStorage.news = [];

    function formatUrl(page) {
        return API_URL + 'news/news_' + _.padStart(page, 5, '0') + '.json';
    }

    function processNews(article) {
        article = article || {};
        article.published_at_str = article.published_at ? moment(article.published_at).calendar() : null;
        return article;
    }

    service.getNews = function getNews(page, noblock) {
        page = _.parseInt(page) || 0;

        if (!_.isEmpty($sessionStorage.news[page])) {
            return $q.resolve($sessionStorage.news[page]);
        }

        return $http.get(formatUrl(page), {'noblock': !!noblock})
            .then(function (response) {
                var articles = _.map(_.get(response, 'data.results'), processNews),
                    result = {
                        'page': page,
                        'articles': articles,
                        'nextPage': _.get(response, 'data.next'),
                        'total': _.get(response, 'data.count')
                    };
                if (!_.isEmpty(articles)) {
                    $sessionStorage.news[page] = result;
                }
                return result;
            })
            .catch(function (response) {
                $log.error(response);
                return {
                    'page': page,
                    'articles': [],
                    'nextPage': null,
                    'total': null
                };
            });
    };

    service.setLastVisit = function setLastVisit(date) {
        date = moment(date || undefined);
        date = date.isValid() ? date : moment();
        $localStorage.lastVisitNews = date;
        return date;
    };

    service.getLastVisit = function getLastVisit() {
        if (!$localStorage.lastVisitNews) {
            return null;
        }
        var date = moment($localStorage.lastVisitNews);
        return date.isValid() ? date : null;
    };

    return service;
});

ludojApp.factory('filterService', function filterService(
    $sessionStorage
) {
    var yearFloor = 1970,
        yearNow = new Date().getFullYear(),
        service = {
            'yearFloor': yearFloor,
            'yearNow': yearNow
        },
        orderingValues = {
            'rg': '-rec_rating,-bayes_rating,-avg_rating',
            'bgg': '-bayes_rating,-rec_rating,-avg_rating',
            'complex': 'complexity,-rec_rating,-bayes_rating,-avg_rating',
            '-complex': '-complexity,-rec_rating,-bayes_rating,-avg_rating',
            'year': 'year,-rec_rating,-bayes_rating,-avg_rating',
            '-year': '-year,-rec_rating,-bayes_rating,-avg_rating',
            'time': 'min_time,-rec_rating,-bayes_rating,-avg_rating',
            '-time': '-max_time,-rec_rating,-bayes_rating,-avg_rating',
            'age': 'min_age,-rec_rating,-bayes_rating,-avg_rating',
            '-age': '-min_age,-rec_rating,-bayes_rating,-avg_rating'
        };

    function validateCountType(playerCountType) {
        var playerCountTypes = {'box': true, 'recommended': true, 'best': true};
        return playerCountTypes[playerCountType] ? playerCountType : 'recommended';
    }

    function validateTimeType(playTimeType) {
        var playTimeTypes = {'min': true, 'max': true};
        return playTimeTypes[playTimeType] ? playTimeType : 'max';
    }

    function validateAgeType(playerAgeType) {
        var playerAgeTypes = {'box': true, 'recommended': true};
        return playerAgeTypes[playerAgeType] ? playerAgeType : 'recommended';
    }

    function validateBoolean(input) {
        var booleans = {'True': true, 'False': true};
        return booleans[input] ? input : null;
    }

    function parseBoolean(input) {
        if (_.isBoolean(input)) {
            return input;
        }

        var integer = _.parseInt(input),
            booleans = {
                'true': true,
                'True': true,
                'false': false,
                'False': false,
                'yes': true,
                'Yes': true,
                'no': false,
                'No': false
            };

        if (_.isInteger(integer)) {
            return !!integer;
        }

        return _.isBoolean(booleans[input]) ? booleans[input] : null;
    }

    function booleanDefault(boolean, default_, ignore) {
        if (ignore) {
            return null;
        }
        boolean = parseBoolean(boolean);
        return _.isBoolean(boolean) ? boolean : default_;
    }

    function booleanString(boolean) {
        boolean = parseBoolean(boolean);
        return !_.isBoolean(boolean) ? null : boolean ? 'True' : 'False';
    }

    function validateOrdering(ordering) {
        return orderingValues[ordering] ? ordering : 'rg';
    }

    function orderingParams(ordering) {
        return orderingValues[ordering] || orderingValues.rg;
    }

    function parseParams(params) {
        params = params || {};

        var user = _.trim(params.for) || _.trim(params.user) || null,
            playerCount = _.parseInt(params.playerCount) || null,
            playTime = _.parseInt(params.playTime) || null,
            playerAge = _.parseInt(params.playerAge) || null,
            excludeRated = booleanDefault(params.excludeRated, true, !user),
            excludeOwned = booleanDefault(params.excludeOwned, true, !user),
            excludeWishlist = booleanDefault(params.excludeWishlist, false, !user),
            excludePlayed = booleanDefault(params.excludePlayed, false, !user),
            excludeClusters = booleanDefault(params.excludeClusters, true, !user),
            similarity = booleanDefault(params.similarity, false, !user),
            yearMin = _.parseInt(params.yearMin),
            yearMax = _.parseInt(params.yearMax),
            ordering = validateOrdering(params.ordering),
            like = _(params.like)
                .split(',')
                .map(_.parseInt)
                .reject(_.isNaN)
                .sortBy()
                .sortedUniq()
                .value();

        return {
            'for': user,
            'excludeRated': excludeRated === false ? false : null,
            'excludeOwned': excludeOwned === false ? false : null,
            'excludeWishlist': excludeWishlist === true ? true : null,
            'excludePlayed': excludePlayed === true ? true : null,
            'excludeClusters': excludeClusters === false ? false : null,
            'similarity': similarity === true ? true : null,
            'like': !_.isEmpty(like) && !user ? like : null,
            'search': _.trim(params.search) || null,
            'playerCount': playerCount,
            'playerCountType': playerCount && validateCountType(params.playerCountType),
            'playTime': playTime,
            'playTimeType': playTime && validateTimeType(params.playTimeType),
            'playerAge': playerAge,
            'playerAgeType': playerAge && validateAgeType(params.playerAgeType),
            'complexityMin': parseFloat(params.complexityMin) || null,
            'complexityMax': parseFloat(params.complexityMax) || null,
            'yearMin': yearMin && yearMin > yearFloor ? yearMin : null,
            'yearMax': yearMax && yearMax <= yearNow ? yearMax : null,
            'cooperative': validateBoolean(params.cooperative),
            'ordering': user || !_.isEmpty(like) || ordering === 'rg' ? null : ordering
        };
    }

    service.paramsFromScope = function paramsFromScope(scope) {
        scope = scope || {};

        var result = {
            'for': scope.user,
            'search': scope.search,
            'cooperative': scope.cooperative,
            'ordering': scope.ordering
        };

        if (scope.count.enabled && scope.count.value) {
            result.playerCount = scope.count.value;
            result.playerCountType = validateCountType(scope.count.type);
        } else {
            result.playerCount = null;
            result.playerCountType = null;
        }

        if (scope.time.enabled && scope.time.value) {
            result.playTime = scope.time.value;
            result.playTimeType = validateTimeType(scope.time.type);
        } else {
            result.playTime = null;
            result.playTimeType = null;
        }

        if (scope.age.enabled && scope.age.value) {
            result.playerAge = scope.age.value;
            result.playerAgeType = validateAgeType(scope.age.type);
        } else {
            result.playerAge = null;
            result.playerAgeType = null;
        }

        if (scope.complexity.enabled && scope.complexity.min && scope.complexity.max) {
            result.complexityMin = scope.complexity.min;
            result.complexityMax = scope.complexity.max;
        } else {
            result.complexityMin = null;
            result.complexityMax = null;
        }

        if (scope.year.enabled && scope.year.min && scope.year.max) {
            result.yearMin = scope.year.min;
            result.yearMax = scope.year.max;
        } else {
            result.yearMin = null;
            result.yearMax = null;
        }

        if (scope.user) {
            result.excludeRated = parseBoolean(_.get(scope, 'exclude.rated'));
            result.excludeOwned = parseBoolean(_.get(scope, 'exclude.owned'));
            result.excludeWishlist = parseBoolean(_.get(scope, 'exclude.wishlist'));
            result.excludePlayed = parseBoolean(_.get(scope, 'exclude.played'));
            result.excludeClusters = parseBoolean(_.get(scope, 'exclude.clusters'));
            result.similarity = parseBoolean(scope.similarity);
        } else {
            result.excludeRated = null;
            result.excludeOwned = null;
            result.excludeWishlist = null;
            result.excludePlayed = null;
            result.excludeClusters = null;
            result.similarity = null;
        }

        result.like = !_.isEmpty(scope.likedGames) && !scope.user ? _.map(scope.likedGames, 'bgg_id') : null;

        return parseParams(result);
    };

    service.getParams = function getParams(params) {
        return parseParams(!params || params.filters ? $sessionStorage.params : params);
    };

    service.setParams = function setParams(params) {
        $sessionStorage.params = parseParams(params);
    };

    service.filtersFromParams = function filtersFromParams(params) {
        var result = {},
            playerSuffix = '',
            ageSuffix = '',
            mainOrdering;

        params = params || {};

        if (params.for) {
            result.user = params.for;
            result.exclude_known = booleanString(booleanDefault(params.excludeRated, true));
            result.exclude_owned = booleanString(booleanDefault(params.excludeOwned, true));
            result.exclude_wishlist = booleanDefault(params.excludeWishlist, false) ? 5 : null;
            result.exclude_play_count = booleanDefault(params.excludePlayed, false) ? 1 : null;
            result.exclude_clusters = booleanString(booleanDefault(params.excludeClusters, true));
            result.model = params.similarity ? 'similarity' : null;
        } else if (!_.isEmpty(params.like)) {
            result.like = params.like;
        } else {
            result.ordering = orderingParams(params.ordering);
            mainOrdering = _.split(result.ordering, ',', 1)[0];
            if (mainOrdering[0] !== '-') {
                result[mainOrdering + '__isnull'] = 'False';
            }
        }

        if (params.search) {
            result.search = params.search;
        }

        if (params.playerCount) {
            playerSuffix = params.playerCountType === 'recommended' ? '_rec'
                    : params.playerCountType === 'best' ? '_best'
                    : '';
            result['min_players' + playerSuffix + '__lte'] = params.playerCount;
            result['max_players' + playerSuffix + '__gte'] = params.playerCount;
        }

        if (params.playTime) {
            result[params.playTimeType + '_time__gt'] = 0;
            result[params.playTimeType + '_time__lte'] = params.playTime;
        }

        if (params.playerAge) {
            ageSuffix = params.playerAgeType === 'recommended' ? '_rec'
                    : '';
            result['min_age' + ageSuffix + '__gt'] = 0;
            result['min_age' + ageSuffix + '__lte'] = params.playerAge;
        }

        if (params.complexityMin && params.complexityMax) {
            result.complexity__gte = params.complexityMin;
            result.complexity__lte = params.complexityMax;
        }

        if (params.yearMin && params.yearMin > yearFloor) {
            result.year__gte = params.yearMin;
        }

        if (params.yearMax && params.yearMax <= yearNow) {
            result.year__lte = params.yearMax;
        }

        if (params.cooperative) {
            result.cooperative = params.cooperative;
        }

        return result;
    };

    service.booleanDefault = booleanDefault;
    service.validateAgeType = validateAgeType;
    service.validateBoolean = validateBoolean;
    service.validateCountType = validateCountType;
    service.validateTimeType = validateTimeType;

    return service;
});
