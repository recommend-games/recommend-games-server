/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp, _ */

'use strict';

ludojApp.controller('FaqController', function FaqController(
    $anchorScroll,
    $http,
    $location,
    $scope,
    $timeout,
    FAQ_URL
) {
    function parseQuestion(question) {
        question.answer_paragraphs = _.split(question.answer, /\n+/);
        question.id = question.id || _.kebabCase(question.question);
        return question;
    }

    $http.get(FAQ_URL)
        .then(function (response) {
            $scope.questions = _.map(response.data, parseQuestion);
            $timeout($anchorScroll);
        });

    $scope.path = $location.path();
    $scope.scroll = $anchorScroll;
});
