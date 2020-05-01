/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global rgApp, _ */

'use strict';

rgApp.controller('FaqController', function FaqController(
    $anchorScroll,
    $http,
    $location,
    $sce,
    $scope,
    $timeout,
    FAQ_URL,
    gamesService
) {
    function parseQuestion(question) {
        question.answer_paragraphs = _(question.answer).split(/\n+/).map($sce.trustAsHtml).value();
        question.id = question.id || _.kebabCase(question.question);
        return question;
    }

    var canonical;

    $http.get(FAQ_URL)
        .then(function (response) {
            $scope.questions = _.map(response.data, parseQuestion);
            $timeout($anchorScroll);
        });

    $scope.path = $location.path();
    $scope.scroll = $anchorScroll;

    gamesService.setTitle('FAQ');
    gamesService.setCanonicalUrl($location.path());
    gamesService.setImage();
    gamesService.setDescription('Frequently asked questions – and their answers.');

    canonical = gamesService.urlAndPath($location.path(), undefined, true);
    $scope.disqusId = canonical.path;
    $scope.disqusUrl = canonical.url;
});
