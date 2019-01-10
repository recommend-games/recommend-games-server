/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _, $ */

'use strict';

ludojApp.controller('NewsController', function NewsController(
    $http,
    $scope
) {
    $http.get('/api/news/news_00000.json')
        .then(function (response) {
            console.log(response);
            $scope.articles = _.get(response, 'data.results');
        })
        .catch(function (reason) {
            console.log(reason);
        });
});
