/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, _ */

'use strict';

var ludojApp = angular.module('ludojApp', [
    'blockUI',
    'ngAnimate',
    'ngRoute',
    'ngStorage',
    'rzModule',
    'toastr'
]);

ludojApp.constant('API_URL', '/api/')
    .constant('APP_TITLE', 'Ludoj – board game recommendations on recommend.games')
    .constant('CANONICAL_URL', 'https://recommend.games/')
    .constant('DEFAULT_IMAGE', 'assets/android-chrome-512x512.png')
    .constant('SITE_DESCRIPTION', 'Top-rated board games as evaluated by our recommendation engine. ' +
        'Find the best board and card games with personal recommendations for your taste!');

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
    }).when('/news', {
        templateUrl: '/partials/news.html',
        controller: 'NewsController'
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
    blockUIConfig.requestFilter = function requestFilter(config) {
        return !_.get(config, 'noblock');
    };

    toastrConfig.autoDismiss = false;
    toastrConfig.positionClass = 'toast-bottom-right';
    toastrConfig.tapToDismiss = true;
    toastrConfig.timeOut = 5 * 60000;
    toastrConfig.extendedTimeOut = 60000;
});
