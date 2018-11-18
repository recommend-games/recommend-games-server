'use strict';

/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*global ludojApp */

ludojApp.controller('FooterController', function FooterController($scope) {
    $scope.yearNow = new Date().getFullYear();
});
