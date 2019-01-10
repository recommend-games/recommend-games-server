/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _ */

'use strict';

ludojApp.directive('gameSquare', function gameSquare() {
    return {
        'restrict': 'AE',
        'templateUrl': '/partials/game-square.html',
        'scope': {
            'game': '=',
            'showRanking': '='
        },
        'controller': function controller($scope) {
            $scope.bgImage = function bgImage(url) {
                return url ? {'background-image': 'url("' + url + '")'} : null;
            };
        }
    };
});

ludojApp.directive('playerCount', function playerCount() {
    return {
        'restrict': 'E',
        'templateUrl': '/partials/player-count.html',
        'scope': {
            'game': '='
        }
    };
});
