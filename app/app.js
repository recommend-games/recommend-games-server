'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global _, URL, angular */ // moment, showdown

var ludojApp = angular.module('ludojApp', []);

ludojApp.controller('GamesController', function GamesController(
    $http,
    $log,
    $scope,
    $window
) {
    function fetchGames(page) {
        page = page || $scope.page || $scope.nextPage;
        var url = '/api/games/',
            params = {'page': page};

        return $http.get(url, {'params': params})
            .then(function (response) {
                $scope.currPage = page;
                if (_.get(response, 'data.previous')) {
                    $scope.prevPage = page - 1;
                }
                if (_.get(response, 'data.next')) {
                    $scope.nextPage = page + 1;
                }

                return _.get(response, 'data.results');
            });
    }

    function fetchAndUpdateGames(page, append) {
        return fetchGames(page)
            .then(function (games) {
                $scope.games = append && !_.isEmpty($scope.games) ? _.concat($scope.games, games) : games;
                return games;
            })
            .catch(function (reason) {
                $log.error(reason);
                // TODO display error
            });
    }

    fetchAndUpdateGames(1, false)
        .then(function () {
            return fetchAndUpdateGames(2, true);
        });

    $scope.fetchGames = fetchAndUpdateGames;

    $scope.open = function open(url) {
        $window.open(url, '_blank');
    };
});
