/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _ */

'use strict';

function bgImage(url) {
    return url ? {'background-image': 'url("' + url + '")'} : null;
}

ludojApp.directive('gameSquare', function gameSquare() {
    return {
        'restrict': 'AE',
        'templateUrl': '/partials/game-square.html',
        'scope': {
            'game': '=',
            'showRanking': '=',
            'thumb': '@',
            'addClass': '@'
        },
        'controller': function controller($scope) {
            $scope.bgImage = bgImage;
        }
    };
});

ludojApp.directive('articleSquare', function articleSquare() {
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

ludojApp.directive('playerCount', function playerCount() {
    return {
        'restrict': 'E',
        'templateUrl': '/partials/player-count.html',
        'scope': {
            'game': '='
        }
    };
});
