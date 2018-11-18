'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global angular */

var ludojApp = angular.module('ludojApp', [
    'blockUI',
    'ngAnimate',
    'ngRoute',
    'rzModule',
    'toastr'
]);

ludojApp.constant('API_URL', '/api/');

ludojApp.config(function (
    $locationProvider,
    $routeProvider,
    blockUIConfig,
    toastrConfig
) {
    $locationProvider
        .html5Mode({
            enabled: false,
            requireBase: false
        })
        .hashPrefix('');

    $routeProvider.when('/game/:id', {
        templateUrl: '/partials/detail.html',
        controller: 'DetailController'
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
