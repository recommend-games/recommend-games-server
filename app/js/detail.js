/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('DetailController', function DetailController(
    $filter,
    $location,
    $q,
    $routeParams,
    $scope,
    gamesService
) {
    var compilationOf = [],
        containedIn = [],
        implementationOf = [],
        implementedBy = [],
        integratesWith = [];

    $scope.implementations = false;
    $scope.expandable = false;
    $scope.expandDescription = false;

    $scope.toggleDescription = function toggleDescription() {
        $scope.expandDescription = !$scope.expandDescription;
    };

    function updateImplementations() {
        $scope.implementations = !_.isEmpty($scope.compilationOf) ||
            !_.isEmpty($scope.containedIn) ||
            !_.isEmpty($scope.implementationOf) ||
            !_.isEmpty($scope.implementedBy) ||
            !_.isEmpty($scope.integratesWith) ||
            !_.isEmpty($scope.similarGames);
        $scope.expandable = !!$scope.implementations;
    }

    gamesService.getGame($routeParams.id)
        .then(function (game) {
            $scope.game = game;
            $scope.emailSubject = encodeURIComponent('Bad link for "' + game.name + '" (' + game.bgg_id + ')');

            gamesService.setTitle(game.name);
            gamesService.setImage(_.head(game.image_url));
            gamesService.setDescription(game.description_short || game.description);

            $('#game-details')
                .append('<script type="application/ld+json">' + $filter('json')(gamesService.jsonLD(game), 0) + '</script>');

            compilationOf = game.compilation_of || [];
            containedIn = game.contained_in || [];
            implementationOf = game.implements || [];
            implementedBy = game.implemented_by || [];
            integratesWith = game.integrates_with || [];

            var promises = _(_.concat(compilationOf, containedIn, implementationOf, implementedBy, integratesWith))
                .uniq()
                .map(function (id) {
                    return gamesService.getGame(id, false, true)
                        .catch(_.constant());
                })
                .value();

            return $q.all(promises);
        })
        .then(function (implementations) {
            implementations = _(implementations)
                .filter()
                .map(function (game) {
                    return [game.bgg_id, game];
                })
                .fromPairs()
                .value();

            function findIds(ids) {
                return _(ids)
                    .map(function (id) {
                        return implementations[id];
                    })
                    .filter()
                    .value();
            }

            $scope.compilationOf = findIds(compilationOf);
            $scope.containedIn = findIds(containedIn);
            $scope.implementationOf = findIds(implementationOf);
            $scope.implementedBy = findIds(implementedBy);
            $scope.integratesWith = findIds(integratesWith);
        })
        .then(updateImplementations)
        .then(function () {
            $(function () {
                $('.tooltip').remove();
                $('[data-toggle="tooltip"]').tooltip();
            });
        });
        // TODO catch errors

    gamesService.getSimilarGames($routeParams.id, 1, true)
        .then(function (response) {
            $scope.similarGames = _.take(_.get(response, 'results'), 5);
        })
        .then(updateImplementations);

    gamesService.setCanonicalUrl($location.path());
});
