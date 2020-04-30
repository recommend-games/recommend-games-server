/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global rgApp, _ */

'use strict';

rgApp.controller('StatsController', function StatsController(
    $location,
    $log,
    $scope,
    gamesService
) {
    var canonical;

    gamesService.getGamesStats()
        .then(function (response) {
            $scope.data = response;
        })
        .catch($log.error);

    gamesService.setTitle('Statistics');
    gamesService.setDescription('Analyses of the Recommend.Games and BoardGameGeek top 100 games.');
    canonical = gamesService.setCanonicalUrl($location.path());
    gamesService.setImage();

    $scope.disqusId = canonical.path;
    $scope.disqusUrl = canonical.url;
});
