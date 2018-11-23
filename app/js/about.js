/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _ */

'use strict';

ludojApp.controller('AboutController', function AboutController(
    $document,
    $location,
    $scope,
    gamesService,
    APP_TITLE
) {
    $document[0].title = 'About Ludoj: how it all works – ' + APP_TITLE;

    gamesService.getGames(1, {
        'ordering': '-avg_rating',
        'num_votes__gte': 100
    })
    .then(function (response) {
        $scope.topAvg = _.head(response.results);
    });

    gamesService.getGames(1, {
        'ordering': '-bayes_rating'
    })
    .then(function (response) {
        $scope.topBayes = _.head(response.results);
    });

    gamesService.setCanonicalUrl($location.path());
});
