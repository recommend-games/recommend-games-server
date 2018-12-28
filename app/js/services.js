/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.factory('gamesService', function gamesService(
    $cacheFactory,
    $log,
    $http,
    $q,
    $sessionStorage,
    API_URL,
    CANONICAL_URL
) {
    var service = {},
        cache = $cacheFactory('ludoj', {'capacity': 1024});

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

    function processGame(game) {
        game.name_short = _.size(game.name) > 50 ? _.truncate(game.name, {'length': 50, 'separator': /,? +/}) : null;
        game.name_url = encodeURIComponent(_.toLower(game.name));

        game.designer_display = join(game.designer_name, ', ', ' & ');
        game.artist_display = join(game.artist_name, ', ', ' & ');
        game.description_array = _.filter(_.map(_.split(game.description, /\n(\s*\n\s*)+/), _.trim));

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
            ];

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

        return game;
    }

    service.getGames = function getGames(page, filters) {
        var url = API_URL + 'games/',
            params = _.isEmpty(filters) ? {} : _.cloneDeep(filters);
        page = page || null;

        if (page) {
            params.page = page;
        }

        if (params.user) {
            url += 'recommend/';
        }

        $log.debug('query parameters', params);

        return $http.get(url, {'params': params})
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
                        var id = _.get(game, 'bgg_id');
                        if (id) {
                            cache.put(id, game);
                        } else {
                            $log.warn('invalid game', game);
                        }
                    });
                }

                return response.data;
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to load games.';
                return $q.reject(response);
            });
    };

    service.getGame = function getGame(id, forceRefresh) {
        id = _.parseInt(id);
        var cached = forceRefresh ? null : cache.get(id);

        if (!_.isEmpty(cached)) {
            return $q.resolve(cached);
        }

        return $http.get(API_URL + 'games/' + id + '/')
            .then(function (response) {
                var responseId = _.get(response, 'data.bgg_id'),
                    game;

                if (id !== responseId) {
                    return $q.reject('Unable to load game.');
                }

                game = processGame(response.data);
                cache.put(id, game);
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
            'image': game.image_url,
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

    function canonicalUrl(path, params) {
        var url = CANONICAL_URL + '#' + (path || '/'),
            qString = _(_.toPairs(params))
                .filter(1)
                .sortBy(0)
                .map(function (v) {
                    return v[0] + '=' + encodeURIComponent(v[1]);
                })
                .join('&');
        return qString ? url + '?' + qString : url;
    }

    service.setCanonicalUrl = function setCanonicalUrl(path, params) {
        var id = 'canonical-url',
            url;

        $('#' + id).remove();

        if (!path) {
            return;
        }

        url = canonicalUrl(path, params);
        $('head').append('<link rel="canonical" href="' + url + '" id="' + id + '" />');
        return url;
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

    function parseParams(params) {
        params = params || {};

        var user = _.trim(params.for) || _.trim(params.user) || null,
            playerCount = _.parseInt(params.playerCount) || null,
            playTime = _.parseInt(params.playTime) || null,
            playerAge = _.parseInt(params.playerAge) || null;

        return {
            'for': user,
            'excludeRated': booleanDefault(params.excludeRated, true, !user),
            'excludeOwned': booleanDefault(params.excludeOwned, true, !user),
            'excludeWishlist': booleanDefault(params.excludeWishlist, false, !user),
            'excludePlayed': booleanDefault(params.excludePlayed, false, !user),
            'excludeClusters': booleanDefault(params.excludeClusters, true, !user),
            'search': _.trim(params.search) || null,
            'playerCount': playerCount,
            'playerCountType': playerCount && validateCountType(params.playerCountType),
            'playTime': playTime,
            'playTimeType': playTime && validateTimeType(params.playTimeType),
            'playerAge': playerAge,
            'playerAgeType': playerAge && validateAgeType(params.playerAgeType),
            'complexityMin': parseFloat(params.complexityMin) || null,
            'complexityMax': parseFloat(params.complexityMax) || null,
            'yearMin': _.parseInt(params.yearMin) || null,
            'yearMax': _.parseInt(params.yearMax) || null,
            'cooperative': validateBoolean(params.cooperative)
        };
    }

    service.paramsFromScope = function paramsFromScope(scope) {
        scope = scope || {};

        var result = {
            'for': scope.user,
            'search': scope.search,
            'cooperative': scope.cooperative
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
        } else {
            result.excludeRated = null;
            result.excludeOwned = null;
            result.excludeWishlist = null;
            result.excludePlayed = null;
            result.excludeClusters = null;
        }

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
            ageSuffix = '';
        params = params || {};

        if (params.for) {
            result.user = params.for;
            result.exclude_known = booleanString(params.excludeRated);
            result.exclude_owned = booleanString(params.excludeOwned);
            result.exclude_wishlist = params.excludeWishlist === true ? 5 : null;
            result.exclude_play_count = params.excludePlayed === true ? 1 : null;
            result.exclude_clusters = booleanString(params.excludeClusters);
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
