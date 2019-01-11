/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('NewsController', function NewsController(
    $http,
    $location,
    $scope,
    gamesService
) {
    $http.get('/api/news/news_00000.json')
        .then(function (response) {
            var articles = _.get(response, 'data.results');
            $scope.articles = articles;
            gamesService.setImage(_.get(articles, '[0].url_thumbnail[0]'));
        });

    gamesService.setTitle('News aggregator');
    gamesService.setDescription('News about board games, aggregated for you from the top sources of the hobby.');
    gamesService.setCanonicalUrl($location.path());
});
