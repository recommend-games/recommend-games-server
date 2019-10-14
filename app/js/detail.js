/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $, moment, Chart */

'use strict';

ludojApp.controller('DetailController', function DetailController(
    $filter,
    $location,
    $log,
    $q,
    $routeParams,
    $scope,
    $timeout,
    gamesService,
    rankingsService
) {
    var compilationOf = [],
        containedIn = [],
        implementationOf = [],
        implementedBy = [],
        integratesWith = [],
        similarPromise = gamesService.getSimilarGames($routeParams.id, 1, true),
        chart = null,
        startDate = moment().subtract(1, 'year'),
        endDate = moment(),
        allRanges = [
            ['90 Days', moment().subtract(90, 'days')],
            ['6 months', moment().subtract(6, 'months')],
            ['1 year', startDate],
            ['2 years', moment().subtract(2, 'years')],
            ['3 years', moment().subtract(3, 'years')],
            ['5 years', moment().subtract(5, 'years')],
            ['10 years', moment().subtract(10, 'years')]
        ];

    $scope.implementations = false;
    $scope.expandable = false;
    $scope.expandDescription = false;
    $scope.chartVisible = false;
    $scope.display = {
        rgFactor: true,
        rgSimilarity: false,
        bgg: true,
        startDate: startDate,
        endDate: endDate
    };

    $scope.toggleDescription = function toggleDescription() {
        $scope.expandDescription = !$scope.expandDescription;
    };

    function updateImplementations() {
        $scope.implementations = !_.isEmpty($scope.compilationOf) ||
            !_.isEmpty($scope.containedIn) ||
            !_.isEmpty($scope.implementationOf) ||
            !_.isEmpty($scope.implementedBy) ||
            !_.isEmpty($scope.integratesWith) ||
            !_.isEmpty($scope.similarGames);
        $scope.expandable = !!$scope.implementations;
    }

    gamesService.getGame($routeParams.id)
        .then(function (game) {
            var without = _.spread(_.without, 1),
                ids,
                promises;

            $scope.game = game;
            $scope.emailSubject = encodeURIComponent('Bad link for "' + game.name + '" (' + game.bgg_id + ')');

            gamesService.setTitle(game.name);
            gamesService.setImage(_.head(game.image_url));
            gamesService.setDescription(game.description_short || game.description);

            $('#game-details')
                .append('<script type="application/ld+json">' + $filter('json')(gamesService.jsonLD(game), 0) + '</script>');

            compilationOf = game.compilation_of || [];
            ids = compilationOf;
            integratesWith = without(game.integrates_with || [], ids);
            ids = _.concat(ids, integratesWith);
            implementationOf = without(game.implements || [], ids);
            ids = _.concat(ids, implementationOf);
            implementedBy = without(game.implemented_by || [], ids);
            ids = _.concat(ids, implementedBy);
            containedIn = without(game.contained_in || [], ids);
            ids = _.concat(ids, containedIn);

            promises = _.map(ids, function (id) {
                return gamesService.getGame(id, false, true)
                    .catch(_.constant());
            });

            similarPromise
                .then(function (response) {
                    $scope.similarGames = _(response.results)
                        .filter(function (game) {
                            return !_.includes(ids, game.bgg_id);
                        })
                        .take(12)
                        .value();
                })
                .then(updateImplementations);

            return $q.all(promises);
        })
        .then(function (implementations) {
            implementations = _(implementations)
                .filter()
                .map(function (game) {
                    return [game.bgg_id, game];
                })
                .fromPairs()
                .value();

            function findIds(ids) {
                return _(ids)
                    .map(function (id) {
                        return implementations[id];
                    })
                    .filter()
                    .value();
            }

            $scope.compilationOf = findIds(compilationOf);
            $scope.containedIn = findIds(containedIn);
            $scope.implementationOf = findIds(implementationOf);
            $scope.implementedBy = findIds(implementedBy);
            $scope.integratesWith = findIds(integratesWith);
        })
        .then(updateImplementations)
        .then(function () {
            $(function () {
                $('.tooltip').remove();
                $('[data-toggle="tooltip"]').tooltip();
            });
        });
        // TODO catch errors

    function makeDataPoints(data, rankingType, startDate, endDate) {
        data = _(data)
            .filter(['ranking_type', rankingType])
            .map(function (item) {
                return {x: moment(item.date), y: item.rank};
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
            backgroundColor: color,
            cubicInterpolationMode: 'monotone'
        };
    }

    function makeDataSets(data, startDate, endDate) {
        var datasets = [
                $scope.display.rgFactor ? makeDataSet(data, 'fac', startDate, endDate, 'R.G', 'rgba(0, 0, 0, 1)') : null,
                $scope.display.rgSimilarity ? makeDataSet(data, 'sim', startDate, endDate, 'R.G sim', 'rgba(100, 100, 100, 1)') : null,
                $scope.display.bgg ? makeDataSet(data, 'bgg', startDate, endDate, 'BGG', 'rgba(255, 81, 0, 1)') : null
            ];
        return _.filter(datasets);
    }

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

    function updateChart() {
        if (_.isNil(chart) || _.isEmpty($scope.rankings)) {
            return;
        }

        chart.data.datasets = makeDataSets($scope.rankings, $scope.display.startDate, $scope.display.endDate);
        chart.update();
    }

    rankingsService.getRankings($routeParams.id, true)
        .then(function (rankings) {
            if (_.isEmpty(rankings)) {
                $scope.chartVisible = false;
                $scope.rankings = null;
                return $q.reject('unable to load rankings');
            }

            $scope.chartVisible = true;
            $scope.rankings = rankings;
            return findElement('#ranking-history');
        })
        .then(function (element) {
            if (_.isNil(element) || _.isEmpty(element)) {
                $scope.chartVisible = false;
                return $q.reject('unable to find canvas element');
            }

            chart = new Chart(element, {
                type: 'line',
                data: {
                    datasets: makeDataSets($scope.rankings, startDate, endDate)
                },
                options: {
                    responsive: true,
                    animation: false,
                    title: {
                        display: false,
                        text: 'Rankings over time'
                    },
                    tooltips: {
                        mode: 'nearest',
                        axis: 'x',
                        intersect: false
                    },
                    hover: {
                        mode: 'nearest',
                        axis: 'x',
                        intersect: true
                    },
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
                                suggestedMax: 10
                            }
                        }]
                    },
                    legend: {
                        display: false
                    }
                }
            });

            return findElement('#date-range');
        })
        .then(function (element) {
            var minDate = moment(_.minBy($scope.rankings, 'date').date),
                ranges = _(allRanges)
                    .filter(function (item) { return item[1] >= minDate; })
                    .map(function (item) { return [item[0], [item[1], endDate]]; })
                    .fromPairs()
                    .value();
            ranges.Max = [minDate, endDate];

            element.daterangepicker({
                startDate: startDate,
                endDate: endDate,
                minDate: minDate,
                maxDate: endDate,
                showDropdowns: true,
                ranges: ranges
            }, function (start, end) {
                $scope.display.startDate = start;
                $scope.display.endDate = end;
                updateChart();
            });
        })
        .catch($log.error);

    $scope.$watchGroup(
        ['display.rgFactor', 'display.rgSimilarity', 'display.bgg'],
        updateChart
    );

    gamesService.setCanonicalUrl($location.path());
});
