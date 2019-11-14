/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global rgApp, _ */

'use strict';

function bgImage(url) {
    return url ? {'background-image': 'url("' + url + '")'} : null;
}

rgApp.directive('gameSquare', function gameSquare() {
    return {
        'restrict': 'AE',
        'templateUrl': '/partials/game-square.html',
        'scope': {
            'game': '=',
            'showRanking': '=',
            'hideScore': '=',
            'thumb': '@',
            'addClass': '@'
        },
        'controller': function controller($scope) {
            $scope.bgImage = bgImage;
        }
    };
});

rgApp.directive('articleSquare', function articleSquare() {
    return {
        'restrict': 'AE',
        'templateUrl': '/partials/article-square.html',
        'scope': {
            'article': '=',
            'addClass': '@'
        },
        'controller': function controller($scope) {
            $scope.bgImage = bgImage;
        }
    };
});

rgApp.directive('playerCount', function playerCount() {
    return {
        'restrict': 'E',
        'templateUrl': '/partials/player-count.html',
        'scope': {
            'game': '='
        }
    };
});
