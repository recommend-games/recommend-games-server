/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global ludojApp */

'use strict';

ludojApp.controller('NavController', function NavController($location, $route, $rootScope, $scope) {
    function updatePath() {
        $scope.path = $location.path();
    }
    $rootScope.$on('$locationChangeSuccess', updatePath);
    updatePath();
});

ludojApp.controller('FooterController', function FooterController($scope) {
    $scope.yearNow = new Date().getFullYear();
});
