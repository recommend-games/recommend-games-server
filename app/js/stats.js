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
            $scope.empty = _.isEmpty(response);
        })
        .catch(function (response) {
            $log.error(response);
            $scope.empty = true;
        });

    gamesService.setTitle('Statistics');
    gamesService.setDescription('Analyses of the Recommend.Games and BoardGameGeek top 100 games.');
    gamesService.setCanonicalUrl($location.path());
    gamesService.setImage();

    canonical = gamesService.urlAndPath($location.path(), undefined, true);
    $scope.disqusId = canonical.path;
    $scope.disqusUrl = canonical.url;
});
