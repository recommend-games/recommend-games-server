'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global ludojApp, _ */

ludojApp.directive('gameSquare', function gameSquare() {
    return {
        'restrict': 'E',
        'templateUrl': '/partials/game-square.html',
        'scope': {
            'game': '='
        },
        'controller': function controller($scope) {
            $scope.bgImage = function bgImage(url) {
                return url ? {'background-image': 'url("' + url + '")'} : null;
            };

            $scope.starClasses = function starClasses(score) {
                return _.map(_.range(1, 6), function (star) {
                    return score >= star ? 'fas fa-star'
                        : score >= star - 0.5 ? 'fas fa-star-half-alt' : 'far fa-star';
                });
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
