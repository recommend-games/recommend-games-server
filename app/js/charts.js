/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, rgApp, _, moment */

'use strict';

rgApp.controller('ChartsController', function ChartsController(
    $location,
    $log,
    $routeParams,
    $scope,
    gamesService
) {
    var rankingTypes = ['cha', 'bgg', 'fac'],
        rankingType = _.includes(rankingTypes, $routeParams.type) ? $routeParams.type : 'cha',
        date = moment($routeParams.date || null),
        titles = {
            'cha': 'Board game charts',
            'bgg': 'BoardGameGeek top 100',
            'fac': 'Recommend.Games top 100'
        };

    gamesService.getCharts(rankingType, date)
        .then(function (charts) {
            var title = titles[rankingType] + ' for ' + charts.date.format('LL'),
                path = '/' + _.split($location.path(), '/')[1] + '/' + rankingType + '/' + charts.date.format('YYYY-MM-DD'),
                canonical;

            $scope.date = charts.date;
            $scope.games = charts.games;
            $scope.title = title;

            gamesService.setTitle(title);
            gamesService.setDescription(title); // TODO
            gamesService.setCanonicalUrl(path);
            gamesService.setImage(_.get(charts, 'games[0].image_url[0]'));

            canonical = gamesService.urlAndPath(path, undefined, true);
            $scope.disqusId = canonical.path;
            $scope.disqusUrl = canonical.url;
        })
        .catch($log.error);
});
