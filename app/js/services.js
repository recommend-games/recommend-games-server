/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, rgApp, _, moment */

'use strict';

rgApp.factory('gamesService', function gamesService(
    $document,
    $localStorage,
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
    var $ = angular.element,
        service = {},
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
        game.description_array = _(game.description)
            .split(/\n(\s*\n\s*)+/)
            .map(_.trim)
            .filter()
            .value();
        game.description_short = _.size(game.description) > 250 ? _.truncate(game.description, {'length': 250, 'separator': /,? +/}) : null;

        game.designer_data = _.isEmpty(game.designer) || _.isEmpty(game.designer_name) ?
                null : _.zipObject(game.designer, game.designer_name);
        game.artist_data = _.isEmpty(game.artist) || _.isEmpty(game.artist_name) ?
                null : _.zipObject(game.artist, game.artist_name);
        game.game_type_data = _.isEmpty(game.game_type) || _.isEmpty(game.game_type_name) ?
                null : _.zipObject(game.game_type, game.game_type_name);
        game.category_data = _.isEmpty(game.category) || _.isEmpty(game.category_name) ?
                null : _.zipObject(game.category, game.category_name);
        game.mechanic_data = _.isEmpty(game.mechanic) || _.isEmpty(game.mechanic_name) ?
                null : _.zipObject(game.mechanic, game.mechanic_name);

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

        if (!_.isEmpty(params.user) || !_.isEmpty(params.like)) {
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

                if (_.isEmpty(params.user) && _.isEmpty(params.like)) {
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

                _.forEach(games, function (game) {
                    putCache(game);
                });

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

    service.getList = function getList(model, noblock, start, end) {
        start = _.isNumber(start) ? start : 0;
        end = _.isNumber(end) ? end : 25;

        if (end <= _.size($localStorage[model]) || $localStorage[model + 'Page'] === 'end') {
            return $q.resolve(_.slice($localStorage[model], start, end));
        }

        function fetchList(page) {
            return $http.get(API_URL + model + '/', {'params': {'page': page}, 'noblock': !!noblock})
                .then(function (response) {
                    var results = _.get(response, 'data.results', []),
                        next = _.get(response, 'data.next'),
                        nextPage = !next || _.isEmpty(results) ? 'end' : page + 1;

                    $localStorage[model] = page === 1 || _.isEmpty($localStorage[model]) ? results
                        : _.concat($localStorage[model], results);
                    $localStorage[model + 'Page'] = nextPage;

                    if (end <= _.size($localStorage[model]) || nextPage === 'end') {
                        return _.slice($localStorage[model], start, end);
                    }

                    return fetchList(page + 1);
                });
        }

        return fetchList($localStorage[model + 'Page'] || 1)
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load list "' + model + '".';
                return $q.reject(response);
            });
    };

    function processDate(data, field) {
        field = field || 'updated_at';

        if (_.isEmpty(data)) {
            data = {};
            data[field] = null;
            data[field + '_str'] = null;
            return data;
        }

        var date = moment(_.get(data, field));
        data[field + '_str'] = date.isValid() ? date.calendar() : null;
        return data;
    }

    service.getModelUpdatedAt = function getModelUpdatedAt(noblock) {
        if (!_.isEmpty($sessionStorage.model_updated_at)) {
            return $q.resolve($sessionStorage.model_updated_at);
        }

        if (!_.isEmpty(_.get($sessionStorage, 'games_stats.updated_at_str'))) {
            return $q.resolve($sessionStorage.games_stats.updated_at_str);
        }

        return $http.get(API_URL + 'games/updated_at/', {'noblock': !!noblock})
            .then(function (response) {
                var data = processDate(response.data, 'updated_at');
                if (!data.updated_at_str) {
                    return $q.reject('Unable to retrieve last update.');
                }
                $sessionStorage.model_updated_at = data.updated_at_str;
                return data.updated_at_str;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to retrieve last update.';
                return $q.reject(response);
            });
    };

    function addRanks(items, fields) {
        fields = _.isEmpty(fields) ? ['count', 'best'] : fields;
        _.forEach(items, function (item, i) {
            var same = i > 0 && _.every(fields, function (field) { return item[field] === items[i - 1][field]; });
            item.rank =  !same ? i + 1 : items[i - 1].rank;
        });
        return items;
    }

    function processStats(stats) {
        stats = processDate(stats, 'updated_at');
        _.forEach(['rg', 'bgg'], function (site) {
            _.forEach(['artist', 'category', 'designer', 'game_type', 'mechanic'], function (field) {
                stats[site + '_top'][field] = addRanks(stats[site + '_top'][field]);
            });
        });
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
                .flatMap(function (v) {
                    return _.isArray(v[1]) ? _.map(v[1], function (vv) { return [v[0], vv]; }) : [v];
                })
                .reject(function (v) { return _.isNil(v[1]) || v[1] === ''; })
                .sortBy(0)
                .map(function (v) {
                    return v[1] === true ? v[0] : v[0] + '=' + encodeURIComponent(v[1]);
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

rgApp.factory('usersService', function usersService(
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

rgApp.factory('personsService', function personsService(
    $http,
    $localStorage,
    $log,
    $q,
    API_URL
) {
    var service = {};

    if (_.isEmpty($localStorage.persons)) {
        $localStorage.persons = {};
    }

    service.getPerson = function getPerson(id, forceRefresh, noblock) {
        id = _.parseInt(id);
        var cached = forceRefresh ? null : $localStorage.persons[id];

        if (!_.isEmpty(cached)) {
            return $q.resolve(cached);
        }

        return $http.get(API_URL + 'persons/' + id + '/', {'noblock': !!noblock})
            .then(function (response) {
                var responseId = _.get(response, 'data.bgg_id'),
                    person;

                if (id !== responseId) {
                    return $q.reject('Unable to load person.');
                }

                person = response.data;
                $localStorage.persons[id] = person;
                return person;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load person.';
                return $q.reject(response);
            });
    };

    return service;
});

rgApp.factory('newsService', function newsService(
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

rgApp.factory('filterService', function filterService(
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

    function parseList(input, sorted) {
        var result = _(input)
            .split(',')
            .map(_.trim)
            .filter();
        if (sorted) {
            result = result.sortBy(_.lowerCase);
        }
        return result.value();
    }

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

        var usersFor = parseList(params.for, true),
            user = !_.isEmpty(usersFor) ? usersFor : parseList(params.user, true),
            playerCount = _.parseInt(params.playerCount) || null,
            playTime = _.parseInt(params.playTime) || null,
            playerAge = _.parseInt(params.playerAge) || null,
            excludeRated = booleanDefault(params.excludeRated, true, _.size(user) !== 1),
            excludeOwned = booleanDefault(params.excludeOwned, true, _.size(user) !== 1),
            excludeWishlist = booleanDefault(params.excludeWishlist, false, _.size(user) !== 1),
            excludePlayed = booleanDefault(params.excludePlayed, false, _.size(user) !== 1),
            excludeClusters = booleanDefault(params.excludeClusters, true, _.size(user) !== 1),
            similarity = booleanDefault(params.similarity, false, _.isEmpty(user)),
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
            'for': _.isEmpty(user) ? null : user,
            'excludeRated': excludeRated === false ? false : null,
            'excludeOwned': excludeOwned === false ? false : null,
            'excludeWishlist': excludeWishlist === true ? true : null,
            'excludePlayed': excludePlayed === true ? true : null,
            'excludeClusters': excludeClusters === false ? false : null,
            'similarity': similarity === true ? true : null,
            'like': !_.isEmpty(like) && _.isEmpty(user) ? like : null,
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
            'gameType': _.parseInt(params.gameType) || null,
            'category': _.parseInt(params.category) || null,
            'mechanic': _.parseInt(params.mechanic) || null,
            'designer': _.parseInt(params.designer) || null,
            'artist': _.parseInt(params.artist) || null,
            'ordering': !_.isEmpty(user) || !_.isEmpty(like) || ordering === 'rg' ? null : ordering
        };
    }

    service.paramsFromScope = function paramsFromScope(scope) {
        scope = scope || {};

        var userList = parseList(scope.user, true),
            result = {
                'for': _.isEmpty(userList) ? null : userList,
                'search': scope.search,
                'cooperative': scope.cooperative,
                'gameType': scope.gameType,
                'category': scope.category,
                'mechanic': scope.mechanic,
                'designer': scope.designer,
                'artist': scope.artist,
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

        if (_.isEmpty(userList)) {
            result.excludeRated = null;
            result.excludeOwned = null;
            result.excludeWishlist = null;
            result.excludePlayed = null;
            result.excludeClusters = null;
            result.similarity = null;
        } else {
            result.excludeRated = parseBoolean(_.get(scope, 'exclude.rated'));
            result.excludeOwned = parseBoolean(_.get(scope, 'exclude.owned'));
            result.excludeWishlist = parseBoolean(_.get(scope, 'exclude.wishlist'));
            result.excludePlayed = parseBoolean(_.get(scope, 'exclude.played'));
            result.excludeClusters = parseBoolean(_.get(scope, 'exclude.clusters'));
            result.similarity = parseBoolean(scope.similarity);
        }

        result.like = !_.isEmpty(scope.likedGames) && _.isEmpty(userList) ? _.map(scope.likedGames, 'bgg_id') : null;

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

        if (!_.isEmpty(params.for)) {
            result.user = params.for;
            result.model = params.similarity ? 'similarity' : null;
            if (_.size(params.for) === 1) {
                result.exclude_known = booleanString(booleanDefault(params.excludeRated, true));
                result.exclude_owned = booleanString(booleanDefault(params.excludeOwned, true));
                result.exclude_wishlist = booleanDefault(params.excludeWishlist, false) ? 5 : null;
                result.exclude_play_count = booleanDefault(params.excludePlayed, false) ? 1 : null;
                result.exclude_clusters = booleanString(booleanDefault(params.excludeClusters, true));
            }
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

        if (params.gameType) {
            result.game_type = params.gameType;
        }

        if (params.category) {
            result.category = params.category;
        }

        if (params.mechanic) {
            result.mechanic = params.mechanic;
        }

        if (params.designer) {
            result.designer = params.designer;
        }

        if (params.artist) {
            result.artist = params.artist;
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

rgApp.factory('rankingsService', function rankingsService(
    $http,
    $log,
    $q,
    API_URL
) {
    var service = {},
        cache = {};

    service.getRankings = function getRankings(id, noblock) {
        id = _.parseInt(id);
        var cached = cache[id];

        if (!_.isEmpty(cached)) {
            return $q.resolve(cached);
        }

        return $http.get(API_URL + 'games/' + id + '/rankings/', {'noblock': !!noblock})
            .then(function (response) {
                var rankings = response.data;

                if (_.isEmpty(rankings)) {
                    return $q.reject('Unable to load rankings.');
                }

                rankings = _.map(rankings, function (item) {
                    item.date = moment(item.date);
                    return item;
                });

                cache[id] = rankings;
                return rankings;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load rankings.';
                return $q.reject(response);
            });
    };

    return service;
});
