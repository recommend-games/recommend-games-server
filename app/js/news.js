/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _ */

'use strict';

ludojApp.controller('NewsController', function NewsController(
    $http,
    $location,
    $scope,
    API_URL,
    gamesService
) {
    function formatUrl(page) {
        return API_URL + 'news/news_' + _.padStart(page, 5, '0') + '.json';
    }

    function fetchNews(page) {
        page = _.parseInt(page) || 0;

        return $http.get(formatUrl(page))
            .then(function (response) {
                var articles = _.get(response, 'data.results');
                $scope.articles = page === 0 || _.isEmpty($scope.articles) ? articles : _.concat($scope.articles, articles);
                $scope.nextPage = _.get(response, 'data.next');
                $scope.total = _.get(response, 'data.count');
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
});
