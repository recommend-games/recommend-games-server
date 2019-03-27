/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, _, moment */

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
    .constant('APP_TITLE', 'Recommend.Games – board game recommendations')
    .constant('CANONICAL_URL', 'https://recommend.games/')
    .constant('DEFAULT_IMAGE', 'assets/android-chrome-512x512.png')
    .constant('SITE_DESCRIPTION', 'Top-rated board games as evaluated by our recommendation engine. ' +
        'Find the best board and card games with personal recommendations for your taste!')
    .constant('GA_TRACKING_ID', 'UA-128891980-1')
    .constant('FAQ_URL', '/assets/faq.json');

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
    }).when('/stats', {
        templateUrl: '/partials/stats.html',
        controller: 'StatsController'
    }).when('/about', {
        templateUrl: '/partials/about.html',
        controller: 'AboutController'
    }).when('/faq', {
        templateUrl: '/partials/faq.html',
        controller: 'FaqController'
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

ludojApp.run(function (
    $locale,
    $localStorage,
    $log,
    $window
) {
    delete $localStorage.cache;

    var locale = _.get($window, 'navigator.languages') || _.get($window, 'navigator.language') || $locale.id,
        momentLocale = moment.locale(locale);

    $log.info('trying to change Moment.js locale to', locale, ', received locale', momentLocale);
});
