/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, ludojApp, _, moment, Chart */

'use strict';

ludojApp.controller('HistoryController', function HistoryController(
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
        startDate = startDateParam.isValid() ? startDateParam : moment().subtract(90, 'days'),
        endDateParam = moment($routeParams.endDate || null),
        endDate = endDateParam.isValid() ? endDateParam : moment().isoWeekday(7),
        top = _.parseInt($routeParams.top) || 100,
        params = {
            'ranking_type': $routeParams.type || 'fac',
            'date__gte': startDate.format('YYYY-MM-DD'),
            'date__lte': endDate.format('YYYY-MM-DD'),
            'top': top
        },
        options = {
            // //Boolean - If we show the scale above the chart data
            // scaleOverlay : false,
            // //Boolean - If we want to override with a hard coded scale
            // scaleOverride : true,
            // //** Required if scaleOverride is true **
            // //Number - The number of steps in a hard coded scale
            // scaleSteps : 100,
            // //Number - The value jump in the hard coded scale
            // scaleStepWidth : -1,
            // //Number - The scale starting value
            // scaleStartValue : 100,
            // //String - Colour of the scale line
            // scaleLineColor : "rgba(0,0,0,.1)",
            // //Number - Pixel width of the scale line
            // scaleLineWidth : 1,
            // //Boolean - Whether to show labels on the scale
            // scaleShowLabels : true,
            // //Interpolated JS string - can access value
            // scaleLabel : "<%=value%>",
            // //String - Scale label font declaration for the scale label
            // scaleFontFamily : "'Arial'",
            // //Number - Scale label font size in pixels
            // scaleFontSize : 12,
            // //String - Scale label font weight style
            // scaleFontStyle : "normal",
            // //String - Scale label font colour
            // scaleFontColor : "#666",
            // ///Boolean - Whether grid lines are shown across the chart
            // scaleShowGridLines : false,
            // //String - Colour of the grid lines
            // scaleGridLineColor : "rgba(0,0,0,.05)",
            // //Number - Width of the grid lines
            // scaleGridLineWidth : 1,
            // //Boolean - Whether the line is curved between points
            // bezierCurve : true,
            // //Boolean - Whether to show a dot for each point
            // pointDot : false,
            // //Number - Radius of each point dot in pixels
            // pointDotRadius : 4,
            // //Number - Pixel width of point dot stroke
            // pointDotStrokeWidth : 2,
            // //Boolean - Whether to show a stroke for datasets
            // datasetStroke : true,
            // //Number - Pixel width of dataset stroke
            // datasetStrokeWidth : 1,
            // //Boolean - Whether to fill the dataset with a colour ################
            // datasetFill : false,
            // //Boolean - Whether to animate the chart
            // animation : false,
            // //Number - Number of animation steps
            // animationSteps : 60,
            // //String - Animation easing effect
            // animationEasing : "easeOutQuart",
            // //Function - Fires when the animation is complete
            // onAnimationComplete : null
            responsive: true,
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
            return findElement('#history-chart');
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
