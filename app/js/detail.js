/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, ludojApp, _, $, moment, Chart */

'use strict';

ludojApp.controller('DetailController', function DetailController(
    $filter,
    $http,
    $location,
    $log,
    $q,
    $routeParams,
    $scope,
    gamesService
) {
    var compilationOf = [],
        containedIn = [],
        implementationOf = [],
        implementedBy = [],
        integratesWith = [],
        similarPromise = gamesService.getSimilarGames($routeParams.id, 1, true);

    $scope.implementations = false;
    $scope.expandable = false;
    $scope.expandDescription = false;
    $scope.chartVisible = false;

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

    function makeDataPoints(data, rankingType) {
        return _(data)
            .filter(['ranking_type', rankingType])
            .map(function (item) {
                return {x: moment(item.date), y: item.rank};
            })
            .sortBy('x')
            .value();
    }

    function makeDataSet(data, rankingType, label, color) {
        var dataPoints = makeDataPoints(data, rankingType);
        return {
            label: label,
            borderColor: color,
            backgroundColor: 'rgba(0, 0, 0, 0)',
            data: dataPoints,
            pointRadius: 0,
            fill: false
        };
    }

    $http.get('/api/games/' + $routeParams.id + '/rankings/', {'params': {'date__gte': moment().subtract(30, 'days').format()}, 'noblock': true})
        .then(function (response) {
            var data = response.data;

            if (_.isEmpty(data)) {
                $scope.chartVisible = false;
                return;
            }

            $scope.chartVisible = true;

            return angular.element(function () {
                var ctx = angular.element('#ranking-history');

                if (_.isNil(ctx) || _.isEmpty(ctx)) {
                    $scope.chartVisible = false;
                    $log.error('unable to find canvas element');
                    return null;
                }

                return new Chart(ctx, {
                    type: 'line',
                    data: {
                        datasets: [
                            makeDataSet(data, 'bgg', 'BGG', 'blue'),
                            makeDataSet(data, 'fac', 'R.G', 'red')
                        ]
                    },
                    options: {
                        responsive: true,
                        title: {
                            display: true,
                            text: 'Rankings over time'
                        },
                        tooltips: {
                            mode: 'index',
                            intersect: false,
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
                        }
                    }
                });
            });
        })
        .catch($log.error);

    gamesService.setCanonicalUrl($location.path());
});
