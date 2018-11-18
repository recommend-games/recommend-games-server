/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('DetailController', function DetailController(
    $location,
    $q,
    $routeParams,
    $scope,
    $window,
    gamesService
) {
    $scope.noImplementations = true;
    $scope.expandable = false;
    $scope.expandDescription = false;

    $scope.back = function back() {
        var params = _.clone($routeParams);
        params.id = null;
        $location.search(params)
            .path('/');
    };

    $scope.open = function open(url) {
        var id = _.parseInt(url);
        if (id) {
            $location.path('/game/' + id);
        } else {
            $window.open(url, '_blank');
        }
    };

    $scope.toggleDescription = function toggleDescription() {
        $scope.expandDescription = !$scope.expandDescription;
    };

    gamesService.getGame($routeParams.id)
        .then(function (game) {
            $scope.game = game;
            return $q.all(_.map(game.implements, function (id) {
                return gamesService.getGame(id);
            }));
        })
        .then(function (implementations) {
            $scope.implementations = implementations;
            $scope.noImplementations = _.isEmpty(implementations);
            $scope.expandable = !$scope.noImplementations;
        })
        .then(function () {
            $(function () {
                $('[data-toggle="tooltip"]').tooltip();
            });
        });
        // TODO catch errors
});
