/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global URL, rgApp, _ */

'use strict';

rgApp.controller('VideosController', function VideosController(
    $routeParams,
    $sce,
    $scope,
    gamesService
) {
    var regex = /\Wv=([\-_A-Za-z0-9]+)/;

    gamesService.getGame($routeParams.id)
        .then(function (game) {
            $scope.game = game;
            $scope.youtubeUrls = _(game.video_url)
                .map(function (raw_url) {
                    var url = new URL(raw_url),
                        matches = regex.exec(url.search);
                    return _.size(matches) >= 2 ? matches[1] : null;
                })
                .filter()
                .map(function (youtubeId) {
                    return $sce.trustAsResourceUrl('https://www.youtube-nocookie.com/embed/' + youtubeId);
                })
                .value();
        });
});
