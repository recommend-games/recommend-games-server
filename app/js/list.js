/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('ListController', function ListController(
    $location,
    $log,
    $filter,
    $q,
    $route,
    $routeParams,
    $scope,
    $timeout,
    filterService,
    gamesService,
    toastr
) {
    var params = filterService.getParams($routeParams);

    function filtersActive() {
        return _.sum([
            !!$scope.count.enabled,
            !!$scope.time.enabled,
            !!$scope.age.enabled,
            !!$scope.complexity.enabled,
            !!$scope.year.enabled,
            !!$scope.cooperative
        ]);
    }

    function fetchGames(page) {
        toastr.clear();

        page = _.parseInt(page) || $scope.page || $scope.nextPage || 1;

        var append = page > 1,
            cachedParams = filterService.getParams(),
            routeParams = filterService.getParams($routeParams),
            parsed = append ? cachedParams : routeParams,
            promise = null,
            cachedGames,
            filters;

        if (!append && ($routeParams.filters || _.isEqual(cachedParams, routeParams))) {
            cachedGames = gamesService.getCachedGames();
            $log.debug('loaded ' + _.size(_.get(cachedGames, 'results')) + ' game(s) from cache');
            promise = !_.isEmpty(cachedGames) ? $q.resolve(cachedGames) : null;
        }

        if (_.isNil(promise)) {
            filters = filterService.filtersFromParams(parsed);
            promise = gamesService.getGames(page, filters);
        }

        return promise
            .catch(function (response) {
                $log.error(response);

                if (response.status !== 404 || !filters.user) {
                    return $q.reject(response);
                }

                toastr.error(
                    "Sorry, this user cannot be found. We'll show general recommendations instead.",
                    'Unable to create recommendations for ' + filters.user
                );

                filters.user = null;
                return gamesService.getGames(page, filters);
            })
            .then(function (response) {
                if (!append) {
                    filterService.setParams(parsed);
                }

                page = response.page || page;
                $scope.currPage = page;
                $scope.prevPage = response.previous ? page - 1 : null;
                $scope.nextPage = response.next ? page + 1 : null;
                $scope.total = response.count;
                $scope.currUser = parsed.for;

                var games = response.results;
                games = append && !_.isEmpty($scope.games) ? _.concat($scope.games, games) : games;
                response.results = games;
                gamesService.setCachedGames(response);

                $scope.games = games;
                $scope.empty = _.isEmpty(games) && !$scope.nextPage;

                if (!append && !_.isEmpty(games)) {
                    $('#games-list')
                        .append('<script type="application/ld+json">' + $filter('json')(gamesService.jsonLD(_.slice(games, 0, 10)), 0) + '</script>');
                }

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
                    $('[data-toggle="tooltip"]').tooltip();
                });
            });
    }

    function updateParams() {
        var parsed = filterService.paramsFromScope($scope);
        parsed.filters = null;
        $route.updateParams(parsed);
    }

    function renderSlider() {
        $timeout(function () {
            $scope.count.options.disabled = !$scope.count.enabled;
            $scope.time.options.disabled = !$scope.time.enabled;
            $scope.age.options.disabled = !$scope.age.enabled;
            $scope.complexity.options.disabled = !$scope.complexity.enabled;
            $scope.year.options.disabled = !$scope.year.enabled;
            $scope.$broadcast('rzSliderForceRender');
        });
    }

    $scope.user = params.for;

    $scope.exclude = {
        'rated': filterService.booleanDefault(params.excludeRated, true),
        'owned': filterService.booleanDefault(params.excludeOwned, true),
        'wishlist': filterService.booleanDefault(params.excludeWishlist, false),
        'played': filterService.booleanDefault(params.excludePlayed, false),
        'clusters': filterService.booleanDefault(params.excludeClusters, true)
    };

    $scope.search = params.search;

    $scope.count = {
        'enabled': !!params.playerCount,
        'value': params.playerCount || 4,
        'type': filterService.validateCountType(params.playerCountType),
        'options': {
            'disabled': !params.playerCount,
            'floor': 1,
            'ceil': 10,
            'step': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'showTicks': 1,
            'showSelectionBar': false
        }
    };

    $scope.time = {
        'enabled': !!params.playTime,
        'value': params.playTime || 60,
        'type': filterService.validateTimeType(params.playTimeType),
        'options': {
            'disabled': !params.playTime,
            'floor': 5,
            'ceil': 240,
            'step': 5,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'ticksArray': _.concat(5, _.range(15, 241, 15)),
            'showSelectionBar': true
        }
    };

    $scope.age = {
        'enabled': !!params.playerAge,
        'value': params.playerAge || 10,
        'type': filterService.validateAgeType(params.playerAgeType),
        'options': {
            'disabled': !params.playerAge,
            'floor': 1,
            'ceil': 21,
            'step': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'ticksArray': _.concat(1, _.range(4, 19, 2), 21),
            'showSelectionBar': true
        }
    };

    $scope.complexity = {
        'enabled': !!(params.complexityMin || params.complexityMax),
        'min': params.complexityMin || 1.0,
        'max': params.complexityMax || 5.0,
        'options': {
            'disabled': !(params.complexityMin || params.complexityMax),
            'floor': 1.0,
            'ceil': 5.0,
            'step': 0.1,
            'precision': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'showTicks': 1,
            'draggableRange': true
        }
    };

    $scope.year = {
        'enabled': !!(params.yearMin || params.yearMax),
        'min': params.yearMin || filterService.yearFloor,
        'max': params.yearMax || filterService.yearNow + 1,
        'options': {
            'disabled': !(params.yearMin || params.yearMax),
            'floor': filterService.yearFloor,
            'ceil': filterService.yearNow + 1,
            'step': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'ticksArray': _.concat(_.range(filterService.yearFloor, filterService.yearNow + 1, 5), filterService.yearNow + 1),
            'draggableRange': true
        }
    };

    $scope.cooperative = params.cooperative;

    $scope.ordering = params.ordering || 'ludoj';

    $scope.fetchGames = fetchGames;
    $scope.pad = _.padStart;
    $scope.isEmpty = _.isEmpty;
    $scope.empty = false;
    $scope.total = null;
    $scope.renderSlider = renderSlider;
    $scope.filtersActive = filtersActive;
    $scope.updateParams = updateParams;
    $scope.selectionActive = false;

    $scope.clearFilters = function clearFilters() {
        $scope.user = null;
        $scope.likedGames = null;
        $scope.search = null;
        $scope.count.enabled = false;
        $scope.time.enabled = false;
        $scope.age.enabled = false;
        $scope.complexity.enabled = false;
        $scope.year.enabled = false;
        $scope.cooperative = null;
        $scope.ordering = 'ludoj';
        updateParams();
    };

    $scope.clearUser = function clearUser() {
        $scope.user = null;
        updateParams();
    };

    $scope.clearField = function clearField(field) {
        $scope[field] = null;
        $('#' + field).focus();
    };

    $scope.toggleSelection = function toggleSelection() {
        $scope.selectionActive = !$scope.selectionActive;
        if ($scope.selectionActive) {
            $scope.user = null;
        }
    };

    function contains(array, game) {
        return _.some(array, ['bgg_id', game.bgg_id]);
    }

    function likeGame(game) {
        if (_.isEmpty($scope.likedGames)) {
            $scope.likedGames = [game];
        } else if (!contains($scope.likedGames, game)) {
            $scope.likedGames.push(game);
        }
        _.remove($scope.popularGames, function (g) {
            return g.bgg_id === game.bgg_id;
        });
    }

    function unlikeGame(game) {
        if (_.isEmpty($scope.popularGames)) {
            $scope.popularGames = [game];
        } else if (!contains($scope.popularGames, game)) {
            $scope.popularGames.push(game);
        }
        _.remove($scope.likedGames, function (g) {
            return g.bgg_id === game.bgg_id;
        });
    }

    function cleanLikedGames(games) {
        _.forEach(games, function (game) {
            if (game) {
                likeGame(game);
            }
        });
        return games;
    }

    function fetchPopularGames(page) {
        page = _.isNumber(page) ? page : 1;
        var start = (page - 1) * 11,
            end = page * 11;
        return gamesService.getPopularGames(start, end, true)
            .then(function (games) {
                $scope.popularGames = _.isEmpty($scope.popularGames) ? games : _.concat($scope.popularGames, games);
                $scope.popularGamesPage = page + 1;
                cleanLikedGames($scope.likedGames);
                return games;
            });
    }

    $scope.contains = contains;
    $scope.likeGame = likeGame;
    $scope.unlikeGame = unlikeGame;
    $scope.fetchPopularGames = fetchPopularGames;

    $scope.$watch('count.enabled', renderSlider);
    $scope.$watch('time.enabled', renderSlider);
    $scope.$watch('age.enabled', renderSlider);
    $scope.$watch('complexity.enabled', renderSlider);
    $scope.$watch('year.enabled', renderSlider);

    fetchGames(1)
        .then(function () {
            $(function () {
                $('#filter-game-form')
                    .on('show.bs.collapse', function () {
                        $('#filter-toggle-icon').removeClass('fa-plus-square').addClass('fa-minus-square');
                    })
                    .on('hide.bs.collapse', function () {
                        $('#filter-toggle-icon').removeClass('fa-minus-square').addClass('fa-plus-square');
                    });
                $('#form-exclude-filters')
                    .on('show.bs.collapse', function () {
                        $('#exclude-filters-icon').removeClass('fa-caret-down').addClass('fa-caret-up');
                    })
                    .on('hide.bs.collapse', function () {
                        $('#exclude-filters-icon').removeClass('fa-caret-up').addClass('fa-caret-down');
                    });
            });
            renderSlider();
        });

    fetchPopularGames(1)
        .then(function () {
            var promises = _.map(params.like, function (id) {
                return gamesService.getGame(id, false, true)
                    .catch(_.constant());
            });

            return $q.all(promises);
        })
        .then(function (games) {
            cleanLikedGames(games);
            $scope.likedGames = _($scope.likedGames)
                .sortBy('num_votes')
                .reverse()
                .value();
        });

    gamesService.setTitle(params.for ? 'Recommendations for ' + params.for : null);
    gamesService.setCanonicalUrl($location.path(), filterService.getParams($routeParams));
    gamesService.setImage();
    gamesService.setDescription();
});
