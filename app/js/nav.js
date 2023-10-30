/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, rgApp, _, moment */

'use strict';

rgApp.controller('NavController', function NavController(
    $location,
    $rootScope,
    $scope,
    $timeout,
    newsService
) {
    var $ = angular.element;

    function updatePath() {
        $scope.path = $location.path();
    }

    function updateNewsCount() {
        newsService.getNews(0, false, true)
            .then(function (response) {
                var lastVisit = newsService.getLastVisit(),
                    count = 0;

                if (!lastVisit || !lastVisit.isValid()) {
                    count = _.size(response.articles);
                } else {
                    count = _(response.articles)
                        .filter(function (article) {
                            var publishedAt = article.published_at ? moment(article.published_at) : null;
                            return publishedAt && publishedAt.isValid() && publishedAt >= lastVisit;
                        })
                        .size();
                }

                $scope.newsCount = _.isNumber(count) ? count : null;
            });
    }

    $rootScope.$on('$locationChangeSuccess', function () {
        $('.navbar-collapse').collapse('hide');
        updatePath();
        if ($location.path() === '/news') {
            $timeout(updateNewsCount, 1000);
        }
    });

    updatePath();
    updateNewsCount();
});

rgApp.controller('FooterController', function FooterController(
    $log,
    $scope,
    metaService
) {
    $scope.yearNow = new Date().getFullYear();

    metaService.getServerVersion(true)
        .then(function (version) {
            $scope.version = version.server_version || version.project_version || null;
        })
        .catch($log.error);
});
