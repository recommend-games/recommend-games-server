/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, ludojApp, _ */

'use strict';

ludojApp.controller('BgaController', function BgaController(
    $location,
    $log,
    $http,
    $q,
    $route,
    $routeParams,
    $scope,
    API_URL,
    BGA_CLIENT_ID,
    filterService,
    gamesService,
    toastr
) {
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

    var $ = angular.element,
        users = {},
        userNames = parseList($routeParams.for, true),
        routeParams = filterService.getParams($routeParams);

    function fetchUser(userName) {
        if (users[userName]) {
            return $q.resolve(users[userName]);
        }

        var params = {
            'client_id': BGA_CLIENT_ID,
            'username': userName,
            'limit': 1
        };

        return $http.get('https://www.boardgameatlas.com/api/reviews', {'params': params})
            .then(function (response) {
                var user = _.get(response, 'data.reviews[0].user.id') || null;
                if (user) {
                    users[userName] = user;
                    return user;
                }
                return null;
            })
            .catch(function (response) {
                $log.error(response);
                return null;
            });
    }

    function fetchGames(page) {
        toastr.clear();

        page = _.parseInt(page) || $scope.page || $scope.nextPage || 1;

        var append = page > 1,
            url = API_URL + 'games/recommend_bga/',
            params = {'page': page},
            promise,
            bgaParams,
            games;

        if (routeParams.similarity) {
            params.model = 'similarity';
        }

        if (_.isEmpty(userNames)) {
            promise = $q.resolve(params);
        } else {
            promise = $q.all(_.map(userNames, fetchUser))
                .then(function (results) {
                    params.user = _.filter(results);
                    return params;
                });
        }

        return promise
            .then(function (params) {
                $log.debug('query parameters', params);
                return $http.get(url, {'params': params});
            })
            .then(function (response) {
                response = response.data;
                page = response.page || page;
                $scope.currPage = page;
                $scope.prevPage = response.previous ? page - 1 : null;
                $scope.nextPage = response.next ? page + 1 : null;
                $scope.total = response.count;
                $scope.currUser = !_.isEmpty(userNames) ? userNames : null;

                games = response.results;
                var ids = _.map(games, 'bga_id');
                bgaParams = {
                    'client_id': BGA_CLIENT_ID,
                    'ids': _.join(ids)
                };

                return $http.get('https://www.boardgameatlas.com/api/search', {'params': bgaParams});
            })
            .then(function (response) {
                var bgaObj = _(response.data.games)
                    .map(function (game) {
                        return [game.id, game];
                    })
                    .fromPairs()
                    .value();

                games = _(games)
                    .map(function (rg) {
                        var bga = bgaObj[rg.bga_id];
                        if (!bga || rg.bga_id !== bga.id) {
                            return null;
                        }
                        rg.rec_rank = rg.rank;
                        rg.rec_rating = rg.score;
                        rg.rec_stars = rg.stars;
                        rg.image_url = [bga.image_url];
                        rg.name = rg.name || bga.name;
                        rg.year = bga.year_published;
                        return rg;
                    })
                    .filter()
                    .value();
                games = append && !_.isEmpty($scope.games) ? _.concat($scope.games, games) : games;

                $scope.games = games;
                $scope.empty = _.isEmpty(games) && !$scope.nextPage;

                return games;
            })
            .catch(function (response) {
                $log.error(response);
                $scope.empty = false;
                $scope.total = null;
                toastr.error(
                    'Sorry, there was an error. Tap to try again...',
                    'Error loading games',
                    {'onTap': function onTap() {
                        return fetchGames(page);
                    }}
                );
            })
            .then(function () {
                $(function () {
                    $('.tooltip').remove();
                    $('[data-toggle~="tooltip"]').tooltip();
                    $('[data-toggle-tooltip~="tooltip"]').tooltip();
                });
            });
    }

    $scope.user = _.join(userNames, ', ');
    $scope.similarity = routeParams.similarity;

    $scope.fetchGames = fetchGames;
    $scope.empty = false;
    $scope.total = null;
    $scope.hideScore = true;

    $scope.updateParams = function updateParams() {
        $route.updateParams({
            'for': parseList($scope.user, true),
            'similarity': $scope.similarity || null
        });
    };

    $scope.clearField = function clearField(field, id) {
        $scope[field] = null;
        id = id || field;
        $('#' + id).focus();
    };

    fetchGames(1);

    gamesService.setTitle(routeParams.for ? 'BGA recommendations for ' + routeParams.for : 'BGA recommendations');
    gamesService.setCanonicalUrl($location.path(), filterService.getParams($routeParams));
    gamesService.setImage();
    gamesService.setDescription();
});
