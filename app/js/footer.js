/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp */

'use strict';

ludojApp.controller('FooterController', function FooterController($scope) {
    $scope.yearNow = new Date().getFullYear();
});
