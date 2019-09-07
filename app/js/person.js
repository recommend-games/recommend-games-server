/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('PersonController', function PersonController(
    $http,
    $q,
    $routeParams,
    $scope,
    API_URL
) {
    var role = $routeParams.role || 'designer',
        params = {
            'role': role,
            'ordering': '-rec_rating,-bayes_rating,-avg_rating'
        },
        personPromise = $http.get(API_URL + 'persons/' + $routeParams.id + '/'),
        gamesPromise = $http.get(API_URL + 'persons/' + $routeParams.id + '/games/', {'params': params});

    $q.all([personPromise, gamesPromise])
        .then(function (results) {
            $scope.person = _.get(results, '[0].data');
            $scope.role = _.capitalize(role);
            $scope.games = _.get(results, '[1].data.results');
        });
});
