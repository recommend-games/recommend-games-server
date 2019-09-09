/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $, moment, Chart */

'use strict';

ludojApp.controller('DetailController', function DetailController(
    $filter,
    $http,
    $location,
    $log,
    $q,
    $routeParams,
    $scope,
    $timeout,
    gamesService
) {
    var compilationOf = [],
        containedIn = [],
        implementationOf = [],
        implementedBy = [],
        integratesWith = [],
        similarPromise = gamesService.getSimilarGames($routeParams.id, 1, true),
        chart = null,
        rankingData = null,
        rankingParams = {'date__gte': moment().subtract(30, 'days').format(), 'window': '7d'};

    $scope.implementations = false;
    $scope.expandable = false;
    $scope.expandDescription = false;
    $scope.chartVisible = false;
    $scope.displayRGData = true;
    $scope.displayBGGData = true;

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

    function makeDataPoints(data, rankingType, field) {
        field = field || 'rank';
        return _(data)
            .filter(['ranking_type', rankingType])
            .map(function (item) {
                return {x: moment(item.date), y: item[field]};
            })
            .sortBy('x')
            .value();
    }

    function makeDataSet(data, rankingType, field, label, color, pointRadius) {
        pointRadius = _.parseInt(pointRadius) || 0;

        var dataPoints = makeDataPoints(data, rankingType, field),
            type = pointRadius ? 'scatter' : 'line',
            options = {
                type: type,
                label: label,
                data: dataPoints,
                pointRadius: pointRadius,
                fill: false
            };

        if (type === 'scatter') {
            options.borderColor = 'rgba(0, 0, 0, 0)';
            options.backgroundColor = 'rgba(0, 0, 0, 0)';
            options.pointBorderColor = color;
            options.pointBackgroundColor = 'rgba(0, 0, 0, 0)';
            options.pointBorderWidth = 1;
        } else {
            options.borderColor = color;
            options.backgroundColor = 'rgba(0, 0, 0, 0)';
        }

        return options;
    }

    function makeDataSets(data) {
        var datasets = [
            $scope.displayRGData ? makeDataSet(data, 'fac', 'rank', 'R.G', 'rgba(0, 0, 0, 0.5)', 2) : null,
            $scope.displayBGGData ? makeDataSet(data, 'bgg', 'rank', 'BGG', 'rgba(255, 81, 0, 0.5)', 2) : null,
            $scope.displayRGData ? makeDataSet(data, 'fac', 'avg', 'R.G trend', 'rgba(0, 0, 0, 1)') : null,
            $scope.displayBGGData ? makeDataSet(data, 'bgg', 'avg', 'BGG trend', 'rgba(255, 81, 0, 1)') : null
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

    $http.get('/api/games/' + $routeParams.id + '/rankings/', {'params': rankingParams, 'noblock': true})
        .then(function (response) {
            rankingData = response.data;

            if (_.isEmpty(rankingData)) {
                $scope.chartVisible = false;
                return;
            }

            $scope.chartVisible = true;
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
                    datasets: makeDataSets(rankingData)
                },
                options: {
                    responsive: true,
                    title: {
                        display: false,
                        text: 'Rankings over time'
                    },
                    tooltips: {
                        mode: 'index',
                        intersect: false,
                        filter: function (item) { return item.datasetIndex <= 1; }
                    },
                    hover: {
                        mode: 'nearest',
                        intersect: true
                    },
                    scales: {
                        xAxes: [{
                            type: 'time',
                            distribution: 'linear'
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
                        display: false,
                        labels: {
                            filter: function (item) { return _.endsWith(item.text, 'trend'); }
                        }
                    }
                }
            });
        })
        .catch($log.error);

    $scope.$watchGroup(['displayRGData', 'displayBGGData'], function () {
        if (_.isNil(chart) || _.isEmpty(rankingData)) {
            return;
        }

        chart.data.datasets = makeDataSets(rankingData);
        chart.update();
    });

    gamesService.setCanonicalUrl($location.path());
});
