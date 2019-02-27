/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _ */

'use strict';

ludojApp.controller('StatsController', function StatsController(
    $location,
    $log,
    $scope,
    gamesService
) {
    gamesService.getGamesStats()
        .then(function (response) {
            $scope.data = response;
        })
        .catch($log.error);

    gamesService.setTitle('Statistics');
    gamesService.setDescription('TODO');
    gamesService.setCanonicalUrl($location.path());
    gamesService.setImage();
});
