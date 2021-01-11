/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, rgApp, _, moment */

'use strict';

rgApp.controller('ChartsController', function ChartsController(
    $log,
    $routeParams,
    $scope,
    gamesService
) {
    var rankingType = $routeParams.type || 'cha',
        date = moment($routeParams.date || null);

    gamesService.getCharts(rankingType, date)
        .then(function (games) {
            $scope.games = games;
        })
        .catch($log.error);
});
