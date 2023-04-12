/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, _, moment */

'use strict';

var rgApp = angular.module('rgApp', [
    'blockUI',
    'ngAnimate',
    'ngRoute',
    'ngStorage',
    'rzModule',
    'toastr'
]);

rgApp.constant('MAINTENANCE_MODE', false)
    .constant('API_URL', '/api/')
    // .constant('API_URL', 'https://api.recommended.games/')
    .constant('NEWS_API_FALLBACK_URL', 'https://news.recommend.games/')
    .constant('APP_TITLE', 'Recommend.Games – board game recommendations')
    .constant('CANONICAL_URL', 'https://recommend.games/')
    .constant('DEFAULT_IMAGE', 'assets/android-chrome-512x512.png')
    .constant('SITE_DESCRIPTION', 'Top-rated board games as evaluated by our recommendation engine. ' +
        'Find the best board and card games with personal recommendations for your taste!')
    .constant('FAQ_URL', '/assets/faq.json')
    .constant('NEW_RANKING_DATE', moment('2022-02-22'));

rgApp.config(function (
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
    }).when('/history/:type', {
        templateUrl: '/partials/history.html',
        controller: 'HistoryController'
    }).when('/history', {
        templateUrl: '/partials/history.html',
        controller: 'HistoryController'
    }).when('/charts/:type/:date', {
        templateUrl: '/partials/charts.html',
        controller: 'ChartsController'
    }).when('/charts/:type', {
        templateUrl: '/partials/charts.html',
        controller: 'ChartsController'
    }).when('/charts', {
        templateUrl: '/partials/charts.html',
        controller: 'ChartsController'
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

rgApp.run(function (
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
