/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('DetailController', function DetailController(
    $document,
    $filter,
    $q,
    $routeParams,
    $scope,
    gamesService,
    APP_TITLE
) {
    $scope.noImplementations = true;
    $scope.expandable = false;
    $scope.expandDescription = false;

    $scope.toggleDescription = function toggleDescription() {
        $scope.expandDescription = !$scope.expandDescription;
    };

    gamesService.getGame($routeParams.id)
        .then(function (game) {
            $scope.game = game;
            $document[0].title = game.name + ' – ' + APP_TITLE;

            $('#game-details')
                .append('<script type="application/ld+json">' + $filter('json')(gamesService.jsonLD(game), 0) + '</script>');

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
