/*jslint browser: true, nomen: true, stupid: true, todo: true */
/*jshint -W097 */
/*global angular, rgApp, _ */

'use strict';

rgApp.controller('ListController', function ListController(
    $http,
    $location,
    $log,
    $filter,
    $q,
    $route,
    $routeParams,
    $scope,
    $timeout,
    API_URL,
    filterService,
    gamesService,
    personsService,
    toastr,
    usersService
) {
    var $ = angular.element,
        params = filterService.getParams($routeParams),
        searchPromise = null,
        userStats = {},
        fetchPopularGames;

    $scope.loadUsers = function loadUsers(user) {
        var userUri = encodeURIComponent(user);

        return $http.get(API_URL + 'users/?search=' + userUri + '&ordering=-updated_at', {'noblock': true})
            .then(function (response) {
                return _(_.get(response, 'data.results', []))
                    .map('name')
                    .uniq()
                    .value();
            })
            .catch(function (reason) {
                $log.error('There has been an error', reason);
                var response = _.get(reason, 'data.detail') || reason;
                response = _.isString(response) ? response : 'Unable to find "' + user + '".';
                return $q.reject(response);
            });
    };

    function filtersActive() {
        return _.sum([
            !!$scope.count.enabled,
            !!$scope.time.enabled,
            !!$scope.age.enabled,
            !!$scope.complexity.enabled,
            !!$scope.year.enabled,
            !!$scope.cooperative,
            !!$scope.gameType,
            !!$scope.category,
            !!$scope.mechanic,
            !!$scope.designer,
            !!$scope.artist
        ]);
    }

    function addSearchGames() {
        $scope.searchGames = gamesService.allGames();
    }

    function fetchSearchGames(search) {
        search = search || _.trim($scope.searchLikedGames);
        return gamesService.getGames(1, {'search': search}, true)
            .then(addSearchGames);
    }

    function toggleDropdown(show) {
        var isShown = !!$('#select-games-dropdown').hasClass('show');
        show = !!show;
        if (show !== isShown) {
            // ugly hack because hide / show don't work
            $('#select-games-search').dropdown('toggle');
            isShown = !isShown;
        }
        return isShown;
    }

    function fetchAndUpdate(search) {
        search = search || _.trim($scope.searchLikedGames);
        $timeout.cancel(searchPromise);
        toggleDropdown(true);
        search = search || _.trim($scope.searchLikedGames);
        return fetchSearchGames(search);
    }

    function updateSearchGames(search) {
        search = search || _.trim($scope.searchLikedGames);
        $timeout.cancel(searchPromise);
        if (!_.isEmpty(search)) {
            searchPromise = $timeout(fetchSearchGames, 500, true, search);
        }
        addSearchGames();
        toggleDropdown(!_.isEmpty(search));
    }

    function fetchGames(page) {
        toastr.clear();

        page = _.parseInt(page) || $scope.page || $scope.nextPage || 1;

        var append = page > 1,
            cachedParams = filterService.getParams(),
            routeParams = filterService.getParams($routeParams),
            parsed = append ? cachedParams : routeParams,
            promise = null,
            cachedGames,
            filters;

        if (!append && ($routeParams.filters || _.isEqual(cachedParams, routeParams))) {
            cachedGames = gamesService.getCachedGames();
            $log.debug('loaded ' + _.size(_.get(cachedGames, 'results')) + ' game(s) from cache');
            promise = !_.isEmpty(cachedGames) ? $q.resolve(cachedGames) : null;
        }

        if (_.isNil(promise)) {
            filters = filterService.filtersFromParams(parsed);
            promise = gamesService.getGames(page, filters);
        }

        return promise
            .catch(function (response) {
                $log.error(response);

                if (response.status !== 404 || _.isEmpty(filters.user)) {
                    return $q.reject(response);
                }

                toastr.error('Unable to create recommendations for "' + _.join(filters.user, ', ') + '"');

                $scope.userNotFound = true;

                filters.user = null;
                return gamesService.getGames(page, filters);
            })
            .then(function (response) {
                if (!append) {
                    filterService.setParams(parsed);
                }

                page = response.page || page;
                $scope.currPage = page;
                $scope.prevPage = response.previous ? page - 1 : null;
                $scope.nextPage = response.next ? page + 1 : null;
                $scope.total = response.count;
                $scope.currUser = parsed.for;

                var games = response.results;
                games = append && !_.isEmpty($scope.games) ? _.concat($scope.games, games) : games;
                response.results = games;
                gamesService.setCachedGames(response);

                $scope.games = games;
                $scope.empty = _.isEmpty(games) && !$scope.nextPage;

                if (!append && !_.isEmpty(games)) {
                    $('#games-list')
                        .append('<script type="application/ld+json">' + $filter('json')(gamesService.jsonLD(_.slice(games, 0, 10)), 0) + '</script>');
                }

                addSearchGames();

                return games;
            })
            .catch(function (response) {
                $log.error(response);
                $scope.empty = false;
                $scope.total = null;
                toastr.error(
                    'Sorry, there was an error. Tap to try again...',
                    'Error loading games',
                    {'onTap': function onTap() {
                        return fetchGames(page);
                    }}
                );
            })
            .then(function () {
                $(function () {
                    $('.tooltip').remove();
                    $('[data-toggle~="tooltip"]').tooltip();
                    $('[data-toggle-tooltip~="tooltip"]').tooltip();
                });
            });
    }

    function updateParams() {
        var parsed = filterService.paramsFromScope($scope);
        parsed.filters = null;
        $route.updateParams(parsed);
    }

    function renderSlider() {
        $timeout(function () {
            $scope.count.options.disabled = !$scope.count.enabled;
            $scope.time.options.disabled = !$scope.time.enabled;
            $scope.age.options.disabled = !$scope.age.enabled;
            $scope.complexity.options.disabled = !$scope.complexity.enabled;
            $scope.year.options.disabled = !$scope.year.enabled;
            $scope.$broadcast('rzSliderForceRender');
        });
    }

    $scope.user = _.join(params.for, ', ');

    $scope.exclude = {
        'rated': filterService.booleanDefault(params.excludeRated, true),
        'owned': filterService.booleanDefault(params.excludeOwned, true),
        'wishlist': filterService.booleanDefault(params.excludeWishlist, false),
        'played': filterService.booleanDefault(params.excludePlayed, false),
        'clusters': filterService.booleanDefault(params.excludeClusters, true)
    };

    $scope.similarity = params.similarity;

    $scope.search = params.search;

    $scope.count = {
        'enabled': !!params.playerCount,
        'value': params.playerCount || 4,
        'type': filterService.validateCountType(params.playerCountType),
        'options': {
            'disabled': !params.playerCount,
            'floor': 1,
            'ceil': 10,
            'step': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'showTicks': 1,
            'showSelectionBar': false
        }
    };

    $scope.time = {
        'enabled': !!params.playTime,
        'value': params.playTime || 60,
        'type': filterService.validateTimeType(params.playTimeType),
        'options': {
            'disabled': !params.playTime,
            'floor': 5,
            'ceil': 240,
            'step': 5,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'ticksArray': _.concat(5, _.range(15, 241, 15)),
            'showSelectionBar': true
        }
    };

    $scope.age = {
        'enabled': !!params.playerAge,
        'value': params.playerAge || 10,
        'type': filterService.validateAgeType(params.playerAgeType),
        'options': {
            'disabled': !params.playerAge,
            'floor': 1,
            'ceil': 21,
            'step': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'ticksArray': _.concat(1, _.range(4, 19, 2), 21),
            'showSelectionBar': true
        }
    };

    $scope.complexity = {
        'enabled': !!(params.complexityMin || params.complexityMax),
        'min': params.complexityMin || 1.0,
        'max': params.complexityMax || 5.0,
        'options': {
            'disabled': !(params.complexityMin || params.complexityMax),
            'floor': 1.0,
            'ceil': 5.0,
            'step': 0.1,
            'precision': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'showTicks': 1,
            'draggableRange': true
        }
    };

    $scope.year = {
        'enabled': !!(params.yearMin || params.yearMax),
        'min': params.yearMin || filterService.yearFloor,
        'max': params.yearMax || filterService.yearNow + 1,
        'options': {
            'disabled': !(params.yearMin || params.yearMax),
            'floor': filterService.yearFloor,
            'ceil': filterService.yearNow + 1,
            'step': 1,
            'hidePointerLabels': true,
            'hideLimitLabels': true,
            'ticksArray': _.concat(_.range(filterService.yearFloor, filterService.yearNow + 1, 5), filterService.yearNow + 1),
            'draggableRange': true
        }
    };

    $scope.cooperative = params.cooperative;
    $scope.gameType = params.gameType;
    $scope.category = params.category;
    $scope.mechanic = params.mechanic;
    $scope.designer = params.designer;
    $scope.designerData = null;
    $scope.artist = params.artist;
    $scope.artistData = null;
    $scope.ordering = params.ordering || 'rg';

    $scope.fetchGames = fetchGames;
    $scope.pad = _.padStart;
    $scope.isEmpty = _.isEmpty;
    $scope.size = _.size;
    $scope.empty = false;
    $scope.total = null;
    $scope.renderSlider = renderSlider;
    $scope.filtersActive = filtersActive;
    $scope.updateParams = updateParams;
    $scope.selectionActive = false;
    $scope.groupRecommendation = _.size(params.for) > 1;
    $scope.userNotFound = false;
    $scope.hideScore = !_.isEmpty(params.for) && params.similarity;
    $scope.statsActive = false;
    $scope.userStats = {};

    $scope.clearFilters = function clearFilters() {
        $scope.user = null;
        $scope.likedGames = null;
        $scope.search = null;
        $scope.count.enabled = false;
        $scope.time.enabled = false;
        $scope.age.enabled = false;
        $scope.complexity.enabled = false;
        $scope.year.enabled = false;
        $scope.cooperative = null;
        $scope.gameType = null;
        $scope.category = null;
        $scope.mechanic = null;
        $scope.designer = null;
        $scope.artist = null;
        $scope.ordering = 'rg';
        updateParams();
    };

    $scope.resetField = function resetField(field) {
        if (_.isEmpty(field)) {
            return;
        }
        $scope[field] = null;
        updateParams();
    };

    $scope.clearField = function clearField(field, id) {
        $scope[field] = null;
        id = id || field;
        $('#' + id).focus();
    };

    function toggleSelection(active) {
        active = _.isBoolean(active) ? active : !$scope.selectionActive;
        $scope.selectionActive = active;
        if (active) {
            // $('#select-games').collapse('show');
            $timeout(function () {
                $('#rec-button-tooltip').tooltip('show');
            }, 1000);
        } else {
            $('.tooltip').remove();
            // $('#select-games').collapse('hide');
        }
    }

    function showPane(pane) {
        $scope.activePane = pane;
        // if (pane === 'bgg') {
        //     $('#bgg-tab').tab('show');
        //     toggleSelection(false);
        // } else if (pane === 'select') {
        //     $('#select-games-tab').tab('show');
        //     toggleSelection(true);
        // }
    }

    $scope.toggleSelection = toggleSelection;
    $scope.showPane = showPane;

    $scope.toggleCollapse = function toggleCollapse(target, show) {
        if (_.isBoolean(show)) {
            return $(target).collapse(show ? 'show' : 'hide');
        }
        return $(target).collapse('toggle');
    };

    function contains(array, game) {
        return _.some(array, ['bgg_id', game.bgg_id]);
    }

    function cleanGames(games) {
        games = _.isArray(games) ? games : [games];
        games = _.reject(games, _.isEmpty);
        var ids = _(games).map('bgg_id').filter().value();

        _.remove($scope.popularGames, function (g) {
            return _.includes(ids, g.bgg_id);
        });

        if (_.isEmpty($scope.popularGames)) {
            fetchPopularGames($scope.popularGamesPage);
        }

        $timeout(function () {
            $(_.size(ids) === 1 ? '#like-' + ids[0] : '.badge-liked-game').tooltip();
        });
    }

    function likeGame(game, noToggle, noClean) {
        if (!noToggle && !$scope.selectionActive) {
            toggleSelection(true);
        }

        if (_.isEmpty(game)) {
            return;
        }

        if (_.isEmpty($scope.likedGames)) {
            $scope.likedGames = [game];
        } else if (!contains($scope.likedGames, game)) {
            $scope.likedGames.push(game);
        }

        if (!noClean) {
            cleanGames(game);
        }
    }

    function unlikeGame(game) {
        if (_.isEmpty(game)) {
            return;
        }

        $('#like-' + game.bgg_id).tooltip('dispose');

        if (_.isEmpty($scope.popularGames)) {
            $scope.popularGames = [game];
        } else if (!contains($scope.popularGames, game)) {
            $scope.popularGames.push(game);
        }

        _.remove($scope.likedGames, function (g) {
            return g.bgg_id === game.bgg_id;
        });
    }

    function cleanLikedGames(games) {
        _.forEach(games, function (game) {
            likeGame(game, true, true);
        });
        cleanGames(games);
        return games;
    }

    fetchPopularGames = function fetchPopularGames(page) {
        page = _.isNumber(page) ? page : 1;
        var start = (page - 1) * 5,
            end = page * 5;
        return gamesService.getPopularGames(start, end, true)
            .then(function (games) {
                $scope.popularGames = _.isEmpty($scope.popularGames) ? games : _.concat($scope.popularGames, games);
                $scope.popularGamesPage = page + 1;
                cleanLikedGames($scope.likedGames);
                addSearchGames(games);
                return games;
            });
    };

    function updateStats(site) {
        if (_.isEmpty(userStats[site])) {
            $scope.statsActive = false;
            $scope.userStats = {};
        } else {
            $scope.statsActive = site;
            $scope.userStats = userStats[site];
        }
        $timeout(function () {
            _.forEach($scope.userStats, function (value, key) {
                $('#progress-bar-' + key).css('width', value + '%');
            });
        });
    }

    $scope.contains = contains;
    $scope.likeGame = likeGame;
    $scope.unlikeGame = unlikeGame;
    $scope.fetchPopularGames = fetchPopularGames;
    $scope.fetchAndUpdate = fetchAndUpdate;
    $scope.updateSearchGames = updateSearchGames;
    $scope.updateStats = updateStats;
    $scope.modelUpdatedAt = null;
    $scope.userUpdatedAt = null;

    $scope.$watch('count.enabled', renderSlider);
    $scope.$watch('time.enabled', renderSlider);
    $scope.$watch('age.enabled', renderSlider);
    $scope.$watch('complexity.enabled', renderSlider);
    $scope.$watch('year.enabled', renderSlider);
    $scope.$watch('user', function () { $scope.groupRecommendation = _.includes($scope.user, ','); });

    fetchGames(1)
        .then(function () {
            $(function () {
                $('#filter-game-form')
                    .on('show.bs.collapse', function () {
                        $('#filter-toggle-icon').removeClass('fa-plus-square').addClass('fa-minus-square');
                    })
                    .on('hide.bs.collapse', function () {
                        $('#filter-toggle-icon').removeClass('fa-minus-square').addClass('fa-plus-square');
                    });
                $('#form-exclude-filters')
                    .on('show.bs.collapse', function () {
                        $('#exclude-filters-icon').removeClass('fa-caret-down').addClass('fa-caret-up');
                    })
                    .on('hide.bs.collapse', function () {
                        $('#exclude-filters-icon').removeClass('fa-caret-up').addClass('fa-caret-down');
                    });
            });

            renderSlider();
        });

    if (params.designer) {
        personsService.getPerson(params.designer)
            .then(function (person) {
                $scope.designerData = person;
            })
            .catch($log.error);
    }

    if (params.artist) {
        personsService.getPerson(params.artist)
            .then(function (person) {
                $scope.artistData = person;
            })
            .catch($log.error);
    }

    fetchPopularGames(1)
        .then(function () {
            var promises = _.map(params.like, function (id) {
                return gamesService.getGame(id, false, true)
                    .catch(_.constant());
            });

            return $q.all(promises);
        })
        .then(function (games) {
            cleanLikedGames(games);
            $scope.likedGames = _($scope.likedGames)
                .sortBy('num_votes')
                .reverse()
                .value();
            if (_.isEmpty(params.for) && !_.isEmpty(params.like)) {
                showPane('select');
            }
        })
        .catch($log.error);

    gamesService.getList('types', true, 0, 250)
        .then(function (gameTypes) {
            $scope.gameTypes = gameTypes;
            $scope.gameTypesSorted = _.sortBy(gameTypes, 'name');
        })
        .catch($log.error);

    gamesService.getList('categories', true, 0, 250)
        .then(function (categories) {
            $scope.categories = categories;
            $scope.categoriesSorted = _.sortBy(categories, 'name');
        })
        .catch($log.error);

    gamesService.getList('mechanics', true, 0, 250)
        .then(function (mechanics) {
            $scope.mechanics = mechanics;
            $scope.mechanicsSorted = _.sortBy(mechanics, 'name');
        })
        .catch($log.error);

    if (_.size(params.for) === 1) {
        usersService.getUserStats(params.for[0], true)
            .then(function (stats) {
                $scope.userUpdatedAt = stats.updated_at_str;
                userStats.rg = stats.rg_top;
                userStats.bgg = stats.bgg_top;
                return updateStats('rg');
            })
            .catch($log.error);
    }

    gamesService.getModelUpdatedAt(true)
        .then(function (updatedAt) {
            $scope.modelUpdatedAt = updatedAt;
        })
        .catch($log.error);

    gamesService.setTitle(!_.isEmpty(params.for) ? 'Recommendations for ' + _.join(params.for, ', ') : null);
    gamesService.setCanonicalUrl($location.path(), filterService.getParams($routeParams));
    gamesService.setImage();
    gamesService.setDescription();
});
