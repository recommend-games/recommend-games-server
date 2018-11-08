'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global _, $, URL, angular */ // moment, showdown

var ludojApp = angular.module('ludojApp', [
    'blockUI',
    'rzModule'
]);

ludojApp.config(function (
    $locationProvider,
    blockUIConfig
) {
    $locationProvider.html5Mode({
        enabled: true,
        requireBase: false
    });

    blockUIConfig.autoBlock = true;
    blockUIConfig.delay = 0;
});

ludojApp.controller('GamesController', function GamesController(
    $http,
    $location,
    $log,
    $scope,
    $timeout,
    $window
) {
    function validateCountType(playerCountType) {
        var playerCountTypes = {'box': true, 'recommended': true, 'best': true};
        return playerCountTypes[playerCountType] ? playerCountType : 'box';
    }

    function validateTimeType(playTimeType) {
        var playTimeTypes = {'min': true, 'max': true};
        return playTimeTypes[playTimeType] ? playTimeType : 'min';
    }

    function validateBoolean(input) {
        var booleans = {'True': true, 'False': true};
        return booleans[input] ? input : null;
    }

    function filtersActive() {
        return !!($scope.playerCountEnabled ||
            $scope.playTimeEnabled ||
            $scope.complexity.enabled ||
            $scope.cooperative);
    }

    function filterValues() {
        var result = {};

        if ($scope.playerCountEnabled && $scope.playerCount) {
            result.playerCount = $scope.playerCount;
            result.playerCountType = validateCountType($scope.playerCountType);
        } else {
            result.playerCount = null;
            result.playerCountType = null;
        }

        if ($scope.playTimeEnabled && $scope.playTime) {
            result.playTime = $scope.playTime;
            result.playTimeType = validateTimeType($scope.playTimeType);
        } else {
            result.playTime = null;
            result.playTimeType = null;
        }

        if ($scope.complexity.enabled && $scope.complexity.min && $scope.complexity.max) {
            result.complexityMin = $scope.complexity.min;
            result.complexityMax = $scope.complexity.max;
        }

        result.cooperative = validateBoolean($scope.cooperative);

        return result;
    }

    function filters() {
        var result = {},
            values = filterValues(),
            playerSuffix = '';

        if (values.playerCount) {
            playerSuffix = values.playerCountType === 'recommended' ? '_rec'
                    : values.playerCountType === 'best' ? '_best'
                    : '';
            result['min_players' + playerSuffix + '__lte'] = values.playerCount;
            result['max_players' + playerSuffix + '__gte'] = values.playerCount;
        }

        if (values.playTime) {
            result[values.playTimeType + '_time__lte'] = values.playTime;
        }

        if (values.complexityMin && values.complexityMax) {
            result.complexity__gte = values.complexityMin;
            result.complexity__lte = values.complexityMax;
        }

        if (values.cooperative) {
            result.cooperative = values.cooperative;
        }

        return result;
    }

    function fetchGames(page, user) {
        page = page || $scope.page || $scope.nextPage || 1;
        user = user || null;

        var url = '/api/games/',
            params = filters();

        params.page = page;

        if (user) {
            url += 'recommend/';
            params.user = user;
        }

        $log.info(params);

        return $http.get(url, {'params': params})
            .then(function (response) {
                $scope.currPage = page;
                $scope.prevPage = _.get(response, 'data.previous') ? page - 1 : null;
                $scope.nextPage = _.get(response, 'data.next') ? page + 1 : null;

                var values = filterValues();
                values.user = user;
                $location.search(values);
                $scope.user = user;
                $scope.currUser = user;

                return _.get(response, 'data.results');
            });
    }

    function fetchAndUpdateGames(page, append, user) {
        return fetchGames(page, user)
            .then(function (games) {
                $scope.games = append && !_.isEmpty($scope.games) ? _.concat($scope.games, games) : games;
                return games;
            })
            .catch(function (reason) {
                $log.error(reason);
                // TODO display error
            });
    }

    function renderSlider() {
        $timeout(function () {
            $scope.complexity.options.disabled = !$scope.complexity.enabled;
            $scope.$broadcast('rzSliderForceRender');
        });
    }

    var search = $location.search(),
        playerCount = _.parseInt(search.playerCount),
        playTime = _.parseInt(search.playTime),
        complexityMin = parseFloat(search.complexityMin),
        complexityMax = parseFloat(search.complexityMax);

    $scope.user = search.user || null;

    $scope.playerCountEnabled = !!playerCount;
    $scope.playerCount = playerCount || 4;
    $scope.playerCountType = validateCountType(search.playerCountType);

    $scope.playTimeEnabled = !!playTime;
    $scope.playTime = playTime || 60;
    $scope.playTimeType = validateTimeType(search.playTimeType);

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

    $scope.cooperative = validateBoolean(search.cooperative);

    $scope.fetchGames = fetchAndUpdateGames;
    $scope.now = _.now();
    $scope.pad = _.padStart;
    $scope.renderSlider = renderSlider;

    $scope.open = function open(url) {
        $window.open(url, '_blank');
    };

    $scope.bgImage = function bgImage(url) {
        return url ? {'background-image': 'url("' + url + '")'} : null;
    };

    $scope.$watch('complexity.enabled', renderSlider);

    fetchAndUpdateGames(1, false, search.user);

    if (filtersActive()) {
        $('#filter-game-form').collapse('show');
        renderSlider();
    }
});
