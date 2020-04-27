/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global rgApp, _ */

'use strict';

rgApp.controller('StatsController', function StatsController(
    $location,
    $log,
    $scope,
    CANONICAL_URL,
    gamesService
) {
    gamesService.getGamesStats()
        .then(function (response) {
            $scope.data = response;
        })
        .catch($log.error);

    gamesService.setTitle('Statistics');
    gamesService.setDescription('Analyses of the Recommend.Games and BoardGameGeek top 100 games.');
    gamesService.setCanonicalUrl($location.path());
    gamesService.setImage();

    $scope.disqusId = gamesService.canonicalPath($location.path());
    $scope.disqusUrl = CANONICAL_URL + $scope.disqusId;
});
