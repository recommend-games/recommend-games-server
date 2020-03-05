import json
import re

from itertools import combinations

import networkx as nx

from tqdm import tqdm

REGEX_ID = re.compile(r'^.+:\s*(\d+)\s*$')

def parse(string):
    if not string or not isinstance(string, str):
        return None
    match = REGEX_ID.match(string)
    return int(match.group(1)) if match else string

def process(item):
    if isinstance(item, dict):
        return {k: process(v) for k, v in item.items()}
    if isinstance(item, list):
        return [process(v) for v in item]
    if isinstance(item, str):
        return parse(item)
    return item

def process_game_str(string):
    game = json.loads(string)
    if not isinstance(game.get('bgg_id'), int):
        return None
    game = process(game)
    game['mechanic_set'] = frozenset(game.get('mechanic') or ())
    return game

with open('../board-game-data/scraped/bgg_GameItem.jl') as f:
    games = map(process_game_str, f)
    games = tuple(game for game in games if game and game.get('rank'))

graph = nx.Graph()
for game in tqdm(games):
    clone = {k: v for k, v in game.items() if isinstance(v, (str, int, float, bool))}
    graph.add_node(game['bgg_id'], **clone)

for a, b in tqdm(combinations(games, r=2)):
    shared = a['mechanic_set'] & b['mechanic_set']
    if shared:
        graph.add_edge(a['bgg_id'], b['bgg_id'], weight=len(shared))
