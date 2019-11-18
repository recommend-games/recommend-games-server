/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, rgApp, _, moment, Chart */

'use strict';

rgApp.controller('HistoryController', function HistoryController(
    $http,
    $location,
    $log,
    $q,
    $routeParams,
    $scope,
    $timeout,
    gamesService,
    API_URL
) {
    var $ = angular.element,
        rankingType = $routeParams.type || 'fac',
        startDateParam = moment($routeParams.startDate || null),
        startDate = startDateParam.isValid() ? startDateParam : moment().subtract(1, 'year'),
        endDateParam = moment($routeParams.endDate || null),
        endDate = endDateParam.isValid() ? endDateParam : moment().isoWeekday(7),
        top = _.max([_.min([_.parseInt($routeParams.top) || 100, 250]), 10]),
        params = {
            'ranking_type': rankingType,
            'date__gte': startDate.format('YYYY-MM-DD'),
            'date__lte': endDate.format('YYYY-MM-DD'),
            'top': top
        },
        options = {
            responsive: false,
            animation: false,
            title: {display: false},
            tooltips: {enabled: false},
            hover: {enabled: false},
            scales: {
                xAxes: [{
                    type: 'time',
                    distribution: 'linear',
                    time: {
                        tooltipFormat: 'LL'
                    }
                }],
                yAxes: [{
                    ticks: {
                        reverse: true,
                        min: 1,
                        max: top
                    }
                }]
            },
            legend: {
                display: true,
                position: 'right'
            }
        };

    $scope.type = rankingType;
    $scope.top = top;
    $scope.startDate = startDate;
    $scope.endDate = endDate;

    function findElement(selector, wait, retries) {
        var element = $(selector);

        if (!_.isNil(element) && !_.isEmpty(element)) {
            return $q.resolve(element);
        }

        retries = _.parseInt(retries);

        if (_.isInteger(retries) && retries <= 0) {
            return $q.reject('unable to find canvas element');
        }

        // make sure wait is between 10ms and 10s
        wait = _.min([_.max([parseFloat(wait) || 100, 10]), 10000]);
        retries = _.isInteger(retries) ? retries - 1 : null;

        return $timeout(function () {
            return findElement(selector, wait * 2, retries);
        }, wait);
    }

    function makeDataPoints(data, rankingType, startDate, endDate) {
        data = _(data)
            .filter(['ranking_type', rankingType])
            .map(function (item) {
                return {x: moment(item.date), y: _.min([item.rank, top + 1])};
            })
            .sortBy('x');
        data = _.isNil(startDate) ? data : data.filter(function (item) { return item.x >= startDate; });
        data = _.isNil(endDate) ? data : data.filter(function (item) { return item.x <= endDate; });
        return data.value();
    }

    function makeDataSet(data, rankingType, startDate, endDate, label, color) {
        var dataPoints = makeDataPoints(data, rankingType, startDate, endDate);
        return {
            type: 'line',
            label: label,
            data: dataPoints,
            pointRadius: 0,
            fill: false,
            borderColor: color,
            borderWidth: 1,
            backgroundColor: color,
            cubicInterpolationMode: 'monotone'
        };
    }

    function makeDataSets(data, rankingType, startDate, endDate) {
        var colors = ["#F9A65A", "#48B0E7", "#F1F156", "#79C36A", "#ECC0F5", "#CD7058", "#95F8EC", "#EB5283"];
        return _.map(data, function (item, index) {
            return makeDataSet(
                item.rankings,
                rankingType,
                startDate,
                endDate,
                _.truncate(item.game.name, {'length': 30, 'separator': /,? +/}),
                colors[index % _.size(colors)]
            );
        });
    }

    $http.get(API_URL + 'games/history/', {'params': params})
        .then(function (response) {
            $log.info(response.data);
            $scope.data = response.data;
            $scope.datasets = makeDataSets(response.data, rankingType, startDate, endDate);
            return findElement('#ludoj-history');
        })
        .then(function (container) {
            var rows = _.size($scope.datasets),
                height = rows * 22 + 100,
                columns = endDate.diff(startDate, 'weeks'),
                width = columns * 20 + 180,
                canvas = $('<canvas id="history-chart" width="' + width + '" height="' + height + '"></canvas>');
            canvas.height(height);
            canvas.width(width);
            canvas.appendTo(container);
            return canvas;
        })
        .then(function (canvas) {
            $log.info(canvas);
            var chart = new Chart(canvas, {
                    type: 'line',
                    data: {datasets: $scope.datasets},
                    options: options
                });
            $scope.chart = chart;
            return chart;
        })
        .then($log.info)
        .catch($log.error);

    gamesService.setTitle('Top ' + top + ' history');
    gamesService.setDescription('Visualization of the top ' + top + ' history');
    gamesService.setCanonicalUrl($location.path()); // TODO depends on type
    gamesService.setImage(); // TODO should be an image of the canvas
});
