/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global rgApp, _ */

'use strict';

rgApp.controller('NewsController', function NewsController(
    $location,
    $scope,
    CANONICAL_URL,
    gamesService,
    newsService
) {
    function fetchNews(page) {
        return newsService.getNews(page)
            .then(function (response) {
                $scope.articles = response.page === 0 || _.isEmpty($scope.articles) ? response.articles
                    : _.concat($scope.articles, response.articles);
                $scope.nextPage = response.nextPage;
                $scope.total = response.total;
            });
    }

    $scope.fetchNews = fetchNews;

    fetchNews(0)
        .then(function () {
            gamesService.setImage(_.get($scope.articles, '[0].url_thumbnail[0]'));
        });

    gamesService.setTitle('News aggregator');
    gamesService.setDescription('News about board games, aggregated for you from the top sources of the hobby.');
    gamesService.setCanonicalUrl($location.path());

    newsService.setLastVisit();

    $scope.disqusId = gamesService.canonicalPath($location.path());
    $scope.disqusUrl = CANONICAL_URL + $scope.disqusId;
});
