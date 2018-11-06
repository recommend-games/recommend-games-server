'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global _, URL, angular */ // moment, showdown

var ludojApp = angular.module('ludojApp', ['blockUI']);

ludojApp.controller('GamesController', function GamesController(
    $http,
    $log,
    $scope,
    $window
) {
    function fetchGames(page, user) {
        page = page || $scope.page || $scope.nextPage;
        var url = '/api/games/',
            params = {'page': page};

        if (user) {
            url += 'recommend/';
            params.user = user;
        }

        return $http.get(url, {'params': params})
            .then(function (response) {
                $scope.currPage = page;
                if (_.get(response, 'data.previous')) {
                    $scope.prevPage = page - 1;
                }
                if (_.get(response, 'data.next')) {
                    $scope.nextPage = page + 1;
                }

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

    fetchAndUpdateGames(1, false);

    $scope.fetchGames = fetchAndUpdateGames;

    $scope.open = function open(url) {
        $window.open(url, '_blank');
    };

    $scope.bgImage = function bgImage(url) {
        return url ? {'background-image': 'url("' + url + '")'} : null;
    };

    $scope.now = _.now();
});
