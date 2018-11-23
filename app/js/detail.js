/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('DetailController', function DetailController(
    $document,
    $filter,
    $location,
    $q,
    $routeParams,
    $scope,
    gamesService,
    APP_TITLE
) {
    var implementationOf = [],
        implementedBy = [];

    $scope.implementations = false;
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

            implementationOf = game.implements || [];
            implementedBy = game.implemented_by || [];

            return $q.all(_.map(_.concat(implementationOf, implementedBy), function (id) {
                return gamesService.getGame(id)
                    .catch(_.constant());
            }));
        })
        .then(function (implementations) {
            implementations = _(implementations)
                .filter()
                .map(function (game) {
                    return [game.bgg_id, game];
                })
                .fromPairs()
                .value();
            $scope.implementationOf = _(implementationOf)
                .map(function (id) {
                    return implementations[id];
                })
                .filter()
                .value();
            $scope.implementedBy = _(implementedBy)
                .map(function (id) {
                    return implementations[id];
                })
                .filter()
                .value();
            $scope.implementations = !_.isEmpty($scope.implementationOf) || !_.isEmpty($scope.implementedBy);
            $scope.expandable = !!$scope.implementations;
        })
        .then(function () {
            $(function () {
                $('[data-toggle="tooltip"]').tooltip();
            });
        });
        // TODO catch errors

    gamesService.setCanonicalUrl($location.path());
});
