/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('ListController', function ListController(
    $document,
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
    toastr,
    APP_TITLE
) {
    $document[0].title = APP_TITLE;

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

        var params = filterService.getParams(append ? null : $routeParams),
            filters = filterService.filtersFromParams(params),
            append = page > 1,
            cachedGames = !append && $routeParams.filters ? gamesService.getCachedGames() : null,
            promise = _.isEmpty(cachedGames) ? gamesService.getGames(page, filters) : $q.resolve(cachedGames);

        return promise
            .then(function (response) {
                filterService.setParams(params);

                page = response.page || page;
                $scope.currPage = page;
                $scope.prevPage = response.previous ? page - 1 : null;
                $scope.nextPage = response.next ? page + 1 : null;
                $scope.total = response.count;
                $scope.currUser = params.for;

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
            .catch(function (reason) {
                $log.error(reason);
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
                    $('[data-toggle="tooltip"]').tooltip();
                });
            });
    }

    function updateParams() {
        var params = filterService.paramsFromScope($scope);
        params.filters = null;
        $route.updateParams(params);
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

    $scope.fetchGames = fetchGames;
    $scope.pad = _.padStart;
    $scope.empty = false;
    $scope.total = null;
    $scope.renderSlider = renderSlider;
    $scope.filtersActive = filtersActive;
    $scope.updateParams = updateParams;

    $scope.clearFilters = function clearFilters() {
        $scope.user = null;
        $scope.search = null;
        $scope.count.enabled = false;
        $scope.time.enabled = false;
        $scope.age.enabled = false;
        $scope.complexity.enabled = false;
        $scope.year.enabled = false;
        $scope.cooperative = null;
        updateParams();
    };

    $scope.clearUser = function clearUser() {
        $scope.user = null;
        updateParams();
    };

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
            });
            renderSlider();
        });

    gamesService.setCanonicalUrl($location.path(), filterService.getParams($routeParams));
});
