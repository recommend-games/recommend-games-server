/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, _, moment */

'use strict';

var rgApp = angular.module('rgApp', [
    'blockUI',
    'ngAnimate',
    'ngDisqus',
    'ngRoute',
    'ngStorage',
    'rzModule',
    'toastr'
]);

rgApp.constant('API_URL', '/api/')
    .constant('APP_TITLE', 'Recommend.Games – board game recommendations')
    .constant('CANONICAL_URL', 'https://recommend.games/')
    .constant('DEFAULT_IMAGE', 'assets/android-chrome-512x512.png')
    .constant('SITE_DESCRIPTION', 'Top-rated board games as evaluated by our recommendation engine. ' +
        'Find the best board and card games with personal recommendations for your taste!')
    .constant('GA_TRACKING_ID', 'UA-128891980-1')
    .constant('FAQ_URL', '/assets/faq.json')
    .constant('BGA_CLIENT_ID', '8jfqHypg2l')
    .constant('DISQUS_SHORT_NAME', 'recommend-games');

rgApp.config(function (
    $disqusProvider,
    $locationProvider,
    $routeProvider,
    DISQUS_SHORT_NAME,
    blockUIConfig,
    toastrConfig
) {
    $disqusProvider.setShortname(DISQUS_SHORT_NAME);

    $locationProvider
        .html5Mode({
            enabled: true,
            requireBase: true
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
    }).when('/stats', {
        templateUrl: '/partials/stats.html',
        controller: 'StatsController'
    }).when('/about', {
        templateUrl: '/partials/about.html',
        controller: 'AboutController'
    }).when('/faq', {
        templateUrl: '/partials/faq.html',
        controller: 'FaqController'
    }).when('/bga', {
        templateUrl: '/partials/bga.html',
        controller: 'BgaController'
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
