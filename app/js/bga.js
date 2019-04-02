/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

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
    filterService,
    gamesService,
    toastr
) {
    var users = {};

    function fetchGames(page) {
        toastr.clear();

        page = _.parseInt(page) || $scope.page || $scope.nextPage || 1;

        var append = page > 1,
            url = API_URL + 'games/recommend_bga/',
            userName = $routeParams.for || null,
            params = {'page': page},
            promise,
            bgaParams,
            games;

        if (!userName) {
            promise = $q.resolve(params);
        } else if (users[userName]) {
            params.user = users[userName];
            promise = $q.resolve(params);
        } else {
            bgaParams = {
                'client_id': 'SB1VGnDv7M',
                'username': userName,
                'limit': 1
            };
            promise = $http.get('https://www.boardgameatlas.com/api/reviews', {'params': bgaParams})
                .then(function (response) {
                    var user = _.get(response, 'data.reviews[0].user.id') || null;
                    if (user) {
                        users[userName] = user;
                        params.user = user;
                    }
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
                $scope.currUser = userName;

                games = response.results;
                var ids = _.map(games, 'bga_id');
                bgaParams = {
                    'client_id': 'SB1VGnDv7M',
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

    $scope.user = $routeParams.for;
    $scope.similarity = $routeParams.similarity;

    $scope.fetchGames = fetchGames;
    $scope.empty = false;
    $scope.total = null;
    $scope.hideScore = $routeParams.for && $routeParams.similarity;

    $scope.updateParams = function updateParams() {
        $route.updateParams({'for': $scope.user || null});
    };

    $scope.clearField = function clearField(field, id) {
        $scope[field] = null;
        id = id || field;
        $('#' + id).focus();
    };

    fetchGames(1);

    gamesService.setTitle();
    gamesService.setCanonicalUrl($location.path(), filterService.getParams($routeParams));
    gamesService.setImage();
    gamesService.setDescription();
});
