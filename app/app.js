'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global _, $, URL, angular */

var ludojApp = angular.module('ludojApp', [
    'blockUI',
    'ngAnimate',
    'ngRoute',
    'rzModule',
    'toastr'
]);

ludojApp.constant('API_URL', '/api/');

ludojApp.config(function (
    $locationProvider,
    $routeProvider,
    blockUIConfig,
    toastrConfig
) {
    $locationProvider
        .html5Mode({
            enabled: false,
            requireBase: false
        })
        .hashPrefix('');

    $routeProvider.when('/:id', {
        templateUrl: 'detail.html',
        controller: 'DetailController'
    }).when('/', {
        templateUrl: 'list.html',
        controller: 'ListController'
    }).otherwise({
        redirectTo: '/'
    });

    blockUIConfig.autoBlock = true;
    blockUIConfig.delay = 0;

    toastrConfig.autoDismiss = false;
    toastrConfig.positionClass = 'toast-bottom-right';
    toastrConfig.tapToDismiss = true;
    toastrConfig.timeOut = 5 * 60000;
    toastrConfig.extendedTimeOut = 60000;
});

ludojApp.factory('gamesService', function gamesService(
    $cacheFactory,
    $log,
    $http,
    $q,
    API_URL
) {
    var service = {},
        cache = $cacheFactory('ludoj', {'capacity': 1024});

    service.getGames = function getGames(page, user, filters) {
        page = page || null;
        user = user || null;

        var url = API_URL + 'games/',
            params = !_.isEmpty(filters) ? _.cloneDeep(filters) : {};

        if (page) {
            params.page = page;
        }

        if (user) {
            url += 'recommend/';
            params.user = user;
        }

        $log.info(params);

        return $http.get(url, {'params': params})
            .then(function (response) {
                var games = _.get(response, 'data.results');

                if (!games) {
                    return $q.reject('Unable to load games.');
                }

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
                var responseId = _.get(response, 'data.bgg_id');

                if (id !== responseId) {
                    return $q.reject('Unable to load game.');
                }

                cache.put(id, response.data);

                return response.data;
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

ludojApp.controller('ListController', function ListController(
    $location,
    $log,
    $scope,
    $timeout,
    $window,
    gamesService,
    toastr
) {
    var search = $location.search(),
        playerCount = _.parseInt(search.playerCount),
        playerAge = _.parseInt(search.playerAge),
        playTime = _.parseInt(search.playTime),
        complexityMin = parseFloat(search.complexityMin),
        complexityMax = parseFloat(search.complexityMax),
        yearMin = _.parseInt(search.yearMin),
        yearMax = _.parseInt(search.yearMax),
        yearFloor = 1970,
        yearNow = new Date().getFullYear();

    function validateCountType(playerCountType) {
        var playerCountTypes = {'box': true, 'recommended': true, 'best': true};
        return playerCountTypes[playerCountType] ? playerCountType : 'box';
    }

    function validateTimeType(playTimeType) {
        var playTimeTypes = {'min': true, 'max': true};
        return playTimeTypes[playTimeType] ? playTimeType : 'min';
    }

    function validateAgeType(playerAgeType) {
        var playerAgeTypes = {'box': true, 'recommended': true};
        return playerAgeTypes[playerAgeType] ? playerAgeType : 'box';
    }

    function validateBoolean(input) {
        var booleans = {'True': true, 'False': true};
        return booleans[input] ? input : null;
    }

    function filtersActive() {
        return !!($scope.count.enabled ||
            $scope.time.enabled ||
            $scope.age.enabled ||
            $scope.complexity.enabled ||
            $scope.year.enabled ||
            $scope.cooperative);
    }

    function filterValues() {
        var result = {};

        result.search = _.trim($scope.search) || null;

        if ($scope.count.enabled && $scope.count.value) {
            result.playerCount = $scope.count.value;
            result.playerCountType = validateCountType($scope.count.type);
        } else {
            result.playerCount = null;
            result.playerCountType = null;
        }

        if ($scope.time.enabled && $scope.time.value) {
            result.playTime = $scope.time.value;
            result.playTimeType = validateTimeType($scope.time.type);
        } else {
            result.playTime = null;
            result.playTimeType = null;
        }

        if ($scope.age.enabled && $scope.age.value) {
            result.playerAge = $scope.age.value;
            result.playerAgeType = validateAgeType($scope.age.type);
        } else {
            result.playerAge = null;
            result.playerAgeType = null;
        }

        if ($scope.complexity.enabled && $scope.complexity.min && $scope.complexity.max) {
            result.complexityMin = $scope.complexity.min;
            result.complexityMax = $scope.complexity.max;
        } else {
            result.complexityMin = null;
            result.complexityMax = null;
        }

        if ($scope.year.enabled && $scope.year.min && $scope.year.max) {
            result.yearMin = $scope.year.min;
            result.yearMax = $scope.year.max;
        } else {
            result.yearMin = null;
            result.yearMax = null;
        }

        result.cooperative = validateBoolean($scope.cooperative);

        return result;
    }

    function filters() {
        var result = {},
            values = filterValues(),
            playerSuffix = '',
            ageSuffix = '';

        if (values.search) {
            result.search = values.search;
        }

        if (values.playerCount) {
            playerSuffix = values.playerCountType === 'recommended' ? '_rec'
                    : values.playerCountType === 'best' ? '_best'
                    : '';
            result['min_players' + playerSuffix + '__lte'] = values.playerCount;
            result['max_players' + playerSuffix + '__gte'] = values.playerCount;
        }

        if (values.playTime) {
            result[values.playTimeType + '_time__gt'] = 0;
            result[values.playTimeType + '_time__lte'] = values.playTime;
        }

        if (values.playerAge) {
            ageSuffix = values.playerAgeType === 'recommended' ? '_rec'
                    : '';
            result['min_age' + ageSuffix + '__gt'] = 0;
            result['min_age' + ageSuffix + '__lte'] = values.playerAge;
        }

        if (values.complexityMin && values.complexityMax) {
            result.complexity__gte = values.complexityMin;
            result.complexity__lte = values.complexityMax;
        }

        if (values.yearMin && values.yearMin > yearFloor) {
            result.year__gte = values.yearMin;
        }

        if (values.yearMax && values.yearMax <= yearNow) {
            result.year__lte = values.yearMax;
        }

        if (values.cooperative) {
            result.cooperative = values.cooperative;
        }

        return result;
    }

    function fetchGames(page, user) {
        toastr.clear();

        page = _.parseInt(page) || $scope.page || $scope.nextPage || 1;

        return gamesService.getGames(page, user, filters())
            .then(function (response) {
                $scope.currPage = page;
                $scope.prevPage = response.previous ? page - 1 : null;
                $scope.nextPage = response.next ? page + 1 : null;

                $scope.total = response.count;

                var values = filterValues();
                values.user = user;
                $location.search(values);
                $scope.user = user;
                $scope.currUser = user;

                return response.results;
            });
    }

    function fetchAndUpdateGames(page, append, user) {
        return fetchGames(page, user)
            .then(function (games) {
                $scope.games = append && !_.isEmpty($scope.games) ? _.concat($scope.games, games) : games;
                $scope.empty = _.isEmpty($scope.games) && !$scope.nextPage;
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
                        return fetchAndUpdateGames(page, append, user);
                    }}
                );
            });
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

    $scope.user = search.user || null;

    $scope.search = search.search || null;

    $scope.count = {
        'enabled': !!playerCount,
        'value': playerCount || 4,
        'type': validateCountType(search.playerCountType),
        'options': {
            'disabled': !playerCount,
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
        'enabled': !!playTime,
        'value': playTime || 60,
        'type': validateTimeType(search.playTimeType),
        'options': {
            'disabled': !playTime,
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
        'enabled': !!playerAge,
        'value': playerAge || 10,
        'type': validateAgeType(search.playerAgeType),
        'options': {
            'disabled': !playerAge,
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
        'enabled': !!(complexityMin || complexityMax),
        'min': complexityMin || 1.0,
        'max': complexityMax || 5.0,
        'options': {
            'disabled': !(complexityMin || complexityMax),
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
        'enabled': !!(yearMin || yearMax),
        'min': yearMin || yearFloor,
        'max': yearMax || yearNow + 1,
        'options': {
            'disabled': !(complexityMin || complexityMax),
            'floor': yearFloor,
            'ceil': yearNow + 1,
            'step': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'ticksArray': _.concat(_.range(yearFloor, yearNow + 1, 5), yearNow + 1),
            'draggableRange': true
        }
    };

    $scope.cooperative = validateBoolean(search.cooperative);

    $scope.fetchGames = fetchAndUpdateGames;
    $scope.yearNow = yearNow;
    $scope.pad = _.padStart;
    $scope.empty = false;
    $scope.total = null;
    $scope.renderSlider = renderSlider;

    $scope.open = function open(url) {
        var id = _.parseInt(url);
        if (id) {
            $location.path('/' + id);
        } else {
            $window.open(url, '_blank');
        }
    };

    $scope.bgImage = function bgImage(url) {
        return url ? {'background-image': 'url("' + url + '")'} : null;
    };

    $scope.starClasses = function starClasses(score) {
        return _.map(_.range(1, 6), function (star) {
            return score >= star ? 'fas fa-star'
                : score >= star - 0.5 ? 'fas fa-star-half-alt' : 'far fa-star';
        });
    };

    $scope.clearFilters = function clearFilters() {
        $scope.user = null;
        $scope.search = null;
        $scope.count.enabled = false;
        $scope.time.enabled = false;
        $scope.age.enabled = false;
        $scope.complexity.enabled = false;
        $scope.year.enabled = false;
        $scope.cooperative = null;
        return fetchAndUpdateGames(1, false);
    };

    $scope.$watch('count.enabled', renderSlider);
    $scope.$watch('time.enabled', renderSlider);
    $scope.$watch('age.enabled', renderSlider);
    $scope.$watch('complexity.enabled', renderSlider);
    $scope.$watch('year.enabled', renderSlider);

    fetchAndUpdateGames(1, false, search.user);

    if (filtersActive()) {
        $('#filter-game-form').collapse('show');
        renderSlider();
    }
});

ludojApp.controller('DetailController', function DetailController(
    $routeParams,
    $scope,
    gamesService
) {
    gamesService.getGame($routeParams.id)
        .then(function (game) {
            $scope.game = game;
        });
});
