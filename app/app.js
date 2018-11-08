'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global _, URL, angular */ // moment, showdown

var ludojApp = angular.module('ludojApp', ['blockUI']);

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
    $window
) {
    function filterValues() {
        var result = {},
            playerCountTypes = {
                'box': true,
                'recommended': true,
                'best': true
            },
            playTimeTypes = {
                'min': true,
                'max': true
            };

        if ($scope.playerCountEnabled && $scope.playerCount) {
            result.playerCount = $scope.playerCount;
            result.playerCountType = playerCountTypes[$scope.playerCountType] ? $scope.playerCountType : 'box';
        } else {
            result.playerCount = null;
            result.playerCountType = null;
        }

        if ($scope.playTimeEnabled && $scope.playTime) {
            result.playTime = $scope.playTime;
            result.playTimeType = playTimeTypes[$scope.playTimeType] ? $scope.playTimeType : 'min';
        } else {
            result.playTime = null;
            result.playTimeType = null;
        }

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

    var search = $location.search(),
        playerCount = _.parseInt(search.playerCount),
        playTime = _.parseInt(search.playTime);

    $scope.user = search.user || null;

    $scope.playerCountEnabled = !!playerCount;
    $scope.playerCount = playerCount || 4;
    $scope.playerCountType = search.playerCountType || 'box';

    $scope.playTimeEnabled = !!playTime;
    $scope.playTime = playTime || 60;
    $scope.playTimeType = search.playTimeType || 'min';

    $scope.fetchGames = fetchAndUpdateGames;
    $scope.now = _.now();
    $scope.pad = _.padStart;

    $scope.open = function open(url) {
        $window.open(url, '_blank');
    };

    $scope.bgImage = function bgImage(url) {
        return url ? {'background-image': 'url("' + url + '")'} : null;
    };

    fetchAndUpdateGames(1, false, search.user);
});
