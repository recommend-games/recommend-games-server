/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _ */

'use strict';

ludojApp.controller('AboutController', function AboutController(
    $location,
    $scope,
    gamesService
) {
    gamesService.getGames(1, {
        'ordering': '-avg_rating',
        'num_votes__gte': 100,
        'compilation': 'False'
    }, true)
        .then(function (response) {
            $scope.topAvg = _.head(response.results);
        });

    gamesService.getGames(1, {
        'ordering': '-bayes_rating',
        'compilation': 'False'
    }, true)
        .then(function (response) {
            $scope.topBayes = _.head(response.results);
        });

    gamesService.setTitle('About Ludoj: how it all works');
    gamesService.setCanonicalUrl($location.path());
});
