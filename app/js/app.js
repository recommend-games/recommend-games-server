/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular */

'use strict';

var ludojApp = angular.module('ludojApp', [
    'addthis',
    'blockUI',
    'ngAnimate',
    'ngRoute',
    'ngStorage',
    'rzModule',
    'toastr'
]);

ludojApp.constant('API_URL', '/api/')
    .constant('APP_TITLE', 'Ludoj – board game recommendations on recommend.games')
    .constant('CANONICAL_URL', 'https://recommend.games/');

ludojApp.config(function (
    $addthisProvider,
    $locationProvider,
    $routeProvider,
    blockUIConfig,
    toastrConfig
) {
    $addthisProvider.config({
        'pubid': 'ra-5bfa99b66f363320'
    });

    $locationProvider
        .html5Mode({
            enabled: false,
            requireBase: false
        })
        .hashPrefix('');

    $routeProvider.when('/game/:id', {
        templateUrl: '/partials/detail.html',
        controller: 'DetailController'
    }).when('/about', {
        templateUrl: '/partials/about.html',
        controller: 'AboutController'
    }).when('/', {
        templateUrl: '/partials/list.html',
        controller: 'ListController'
    }).otherwise({
        redirectTo: '/'
    });

    blockUIConfig.autoBlock = true;
    blockUIConfig.delay = 0;

    toastrConfig.autoDismiss = false;
    toastrConfig.positionClass = 'toast-bottom-right';
    toastrConfig.tapToDismiss = true;
    toastrConfig.timeOut = 5 * 60000;
    toastrConfig.extendedTimeOut = 60000;
});
