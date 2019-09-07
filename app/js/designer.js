/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('DesignerController', function DesignerController(
    $http,
    $q,
    $routeParams,
    $scope,
    API_URL
) {
    var params = {
            'role': 'designer',
            'ordering': '-rec_rating,-bayes_rating,-avg_rating'
        },
        personPromise = $http.get(API_URL + 'persons/' + $routeParams.id + '/'),
        gamesPromise = $http.get(API_URL + 'persons/' + $routeParams.id + '/games/', {'params': params});

    $q.all([personPromise, gamesPromise])
        .then(function (results) {
            $scope.designer = _.get(results, '[0].data');
            $scope.games = _.get(results, '[1].data.results');
        });
});
