'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global _, URL, angular */ // moment, showdown

var ludojApp = angular.module('ludojApp', []);

ludojApp.controller('GamesController', function GamesController(
    $http,
    $log,
    $q,
    $scope
) {
    function fetchGames(page) {
        page = page || $scope.page;
        var url = '/api/games/',
            params = {'page': page};

        return $http.get(url, {'params': params})
            .then(function (response) {
                return _.get(response, 'data.results');
            })
            .catch(function (response) {
                $log.error(response);

                return $q.reject(response);
            });
    }

    function fetchAndUpdateGames(page) {
        return fetchGames(page)
            .then(function (games) {
                $scope.games = games;
                return games;
            })
            .catch(function (reason) {
                $log.error(reason);
                // TODO display error
            });
    }

    fetchAndUpdateGames(1);

    $scope.fetchGames = fetchAndUpdateGames;
});
