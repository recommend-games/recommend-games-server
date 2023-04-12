/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, rgApp, _, moment, Chart */

'use strict';

rgApp.controller('DetailController', function DetailController(
    $filter,
    $location,
    $log,
    $q,
    $routeParams,
    $sce,
    $scope,
    $timeout,
    MAINTENANCE_MODE,
    NEW_RANKING_DATE,
    gamesService,
    rankingsService
) {
    var $ = angular.element,
        compilationOf = [],
        containedIn = [],
        implementationOf = [],
        implementedBy = [],
        integratesWith = [],
        startDate = moment().subtract(1, 'year'),
        endDate = moment().isoWeekday(7),
        allRanges = [
            ['90 Days', moment().subtract(90, 'days')],
            ['6 months', moment().subtract(6, 'months')],
            ['1 year', startDate],
            ['2 years', moment().subtract(2, 'years')],
            ['3 years', moment().subtract(3, 'years')],
            ['5 years', moment().subtract(5, 'years')],
            ['10 years', moment().subtract(10, 'years')]
        ];

    $scope.maintenanceMode = false;
    $scope.maintenanceMessage = null;
    $scope.errorMessage = null;

    $scope.implementations = false;
    $scope.expandable = false;
    $scope.expandDescription = false;
    $scope.chart = null;
    $scope.chartVisible = false;
    $scope.rankings = null;
    $scope.display = {
        rg: true,
        factor: true,
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
            !_.isEmpty($scope.integratesWith);
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
        })
        .catch(function (response) {
            $log.error(response);

            if (MAINTENANCE_MODE) {
                $scope.maintenanceMode = true;
                $scope.maintenanceMessage = $sce.trustAsHtml('For more details, please read <a href="https://blog.recommend.games/posts/announcement-hiatus/">this blog post</a>.');
            } else {
                $scope.errorMessage = 'Unable to load the game. 😢 Please try again later…';
            }
        });

    function makeDataPoints(data, rankingType, startDate, endDate) {
        data = _(data)
            .filter(['ranking_type', rankingType])
            .map(function (item) {
                return {x: item.date, y: item.rank};
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
                $scope.display.rg ? makeDataSet(data, 'r_g', startDate, endDate, 'R.G', 'rgba(0, 0, 0, 1)') : null,
                $scope.display.factor ? makeDataSet(data, 'fac', startDate, endDate, 'Old', 'rgba(100, 100, 100, 1)') : null,
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
        if (_.isNil($scope.chart) || _.isEmpty($scope.rankings)) {
            return;
        }

        $scope.chart.data.datasets = makeDataSets($scope.rankings, $scope.display.startDate, $scope.display.endDate);
        $scope.chart.update();
    }

    function bestRanking(rankings, rankingType) {
        rankingType = rankingType || 'bgg';
        return _(rankings)
            .filter({'ranking_type': rankingType})
            .orderBy(['rank', 'date'], ['asc', 'desc'])
            .head();
    }

    rankingsService.getRankings($routeParams.id, true)
        .then(function (rankings) {
            if (_.isEmpty(rankings)) {
                $scope.chart = null;
                $scope.chartVisible = false;
                $scope.rankings = null;
                $scope.bestRankingBGG = null;
                $scope.bestRankingRG = null;

                return $q.reject('unable to load rankings');
            }

            $scope.chartVisible = true;
            $scope.rankings = rankings;
            $scope.bestRankingBGG = bestRanking(rankings, 'bgg');
            $scope.bestRankingRG = moment() >= NEW_RANKING_DATE ? bestRanking(rankings, 'r_g') : bestRanking(rankings, 'fac');

            return findElement('#ranking-history-container');
        })
        .then(function (container) {
            if (_.isNil(container) || _.isEmpty(container)) {
                $scope.chart = null;
                $scope.chartVisible = false;
                return $q.reject('unable to create canvas');
            }

            container.children().remove();
            var element = $('<canvas id="ranking-history"></canvas>').appendTo(container);

            $scope.chart = new Chart(element, {
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

            return findElement('#date-range-container');
        })
        .then(function (container) {
            if (_.isNil(container) || _.isEmpty(container)) {
                return $q.reject('unable to create date range picker');
            }

            container.children().remove();
            var element = $('<input type="text" id="date-range" class="form-control" />').appendTo(container),
                minDate = _.minBy($scope.rankings, 'date').date,
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
        ['display.rg', 'display.factor', 'display.bgg'],
        updateChart
    );

    gamesService.setCanonicalUrl($location.path());
});
