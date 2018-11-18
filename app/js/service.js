'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global ludojApp, _ */

ludojApp.factory('gamesService', function gamesService(
    $cacheFactory,
    $log,
    $http,
    $q,
    API_URL
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

    function processGame(game) {
        game.name_short = _.size(game.name) > 50 ? _.truncate(game.name, {'length': 50, 'separator': /,? +/}) : null;

        game.designer_display = join(game.designer_name, ', ', ' & ');
        game.artist_display = join(game.artist_name, ', ', ' & ');
        game.description_array = _.filter(_.map(_.split(game.description, /\n(\s*\n\s*)+/), _.trim));

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
        game.complexity_string = between(1, game.complexity, 5) ? complexities[_.round(game.complexity)] + ' complexity' : null;
        game.cooperative_string = game.cooperative === true ? 'cooperative' : game.cooperative === false ? 'competitive' : null;

        return game;
    }

    service.getGames = function getGames(page, filters, user) {
        page = page || null;
        user = user || _.get(filters, 'user') || null;

        var url = API_URL + 'games/',
            params = _.isEmpty(filters) ? {} : _.cloneDeep(filters);

        if (page) {
            params.page = page;
        }

        if (user) {
            url += 'recommend/';
            params.user = user;
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

                if (!user) {
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

    return service;
});
