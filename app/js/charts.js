/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, rgApp, _, moment */

'use strict';

rgApp.controller('ChartsController', function ChartsController(
    $location,
    $log,
    $q,
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
        },
        chartsPromise,
        datesPromise;

    $scope.rankingType = rankingType;

    chartsPromise = gamesService.getCharts(rankingType, date)
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

            return charts.date;
        })
        .catch($log.error);

    datesPromise = gamesService.getChartDates(rankingType, true)
        .then(function (dates) {
            $scope.dates = dates;
            return dates;
        })
        .catch($log.error);

    $q.all([chartsPromise, datesPromise])
        .then(function (values) {
            var chartsDate = values[0],
                dates = values[1],
                index = _.findIndex(dates, function (d) {
                    return d.isSameOrAfter(chartsDate, 'day');
                });

            if (index < 0) {
                index = _.size(dates) - 1;
            }

            $scope.first = index <= 0 ? null : dates[0];
            $scope.prev = index <= 1 ? null : dates[index - 1];
            $scope.prevEllipsis = !!$scope.first && !!$scope.prev && (index > 2);
            $scope.next = index >= _.size(dates) - 2 ? null : dates[index].isSame(chartsDate, 'day') ? dates[index + 1] : dates[index];
            $scope.last = index >= _.size(dates) - 1 ? null : dates[_.size(dates) - 1];
            $scope.nextEllipsis = !!$scope.next && !!$scope.last && (index < _.size(dates) - 3);
        })
        .catch($log.error);
});
