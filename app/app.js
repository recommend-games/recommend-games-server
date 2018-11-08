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
    function filters() {
        var result = {},
            playerSuffix = '';

        if ($scope.playerCountEnabled && $scope.playerCount) {
            playerSuffix = $scope.playerCountType === 'recommended' ? '_rec'
                    : $scope.playerCountType === 'best' ? '_best'
                    : '';
            result['min_players' + playerSuffix + '__lte'] = $scope.playerCount;
            result['max_players' + playerSuffix + '__gte'] = $scope.playerCount;
        }

        if ($scope.playTimeEnabled && $scope.playTime) {
            result[$scope.playTimeType + '_time__lte'] = $scope.playTime;
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

                $location.search('user', user);
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

    fetchAndUpdateGames(1, false, $location.search().user);

    $scope.fetchGames = fetchAndUpdateGames;

    $scope.open = function open(url) {
        $window.open(url, '_blank');
    };

    $scope.bgImage = function bgImage(url) {
        return url ? {'background-image': 'url("' + url + '")'} : null;
    };

    $scope.now = _.now();
    $scope.pad = _.padStart;

    $scope.playerCount = 4;
    $scope.playerCountType = 'box';
    $scope.playTime = 60;
    $scope.playTimeType = 'min';
});
