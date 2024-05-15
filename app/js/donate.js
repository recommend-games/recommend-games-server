/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global rgApp, _ */

'use strict';

rgApp.controller('DonateController', function DonateController(
    $location,
    gamesService
) {
    gamesService.setTitle('Donate to Recommend.Games');
    gamesService.setCanonicalUrl($location.path());
    gamesService.setImage();
    gamesService.setDescription('Recommend.Games is a free service that helps you find the best board games for you. ' +
        'If you enjoy using it, please consider donating to help keep the site running.');
});
