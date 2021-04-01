#!/usr/bin/env python3

import collections
import click
import itertools
import json
import multiprocessing
import networkx
import numpy
import random
import scipy


def sample_coordinates():
    return (numpy.random.rand(), numpy.random.rand())


def truncated_exponential(rmin = 0, rmax = 2**0.5):
    while True:
        r = numpy.random.exponential(scale = 0.05)
        if rmin <= r < rmax:
            return r


def pick_target(nearest_neighbours):
    (_, rmax) = nearest_neighbours[-1]
    r = truncated_exponential(rmax = rmax)
    ix = 0
    while nearest_neighbours[ix][1] < r:
        ix += 1
    return nearest_neighbours[ix][0]


def generate_graph(num_nodes):
    the_nodes = list(range(1, num_nodes+1))

    # sample node positions in the unit square
    nodes = { node : sample_coordinates()
                for node in the_nodes
            }

    # connect nodes based on their local neighbourhood using a Voronoi tesselation
    points        = numpy.array(list(nodes.values()))
    triangulation = scipy.spatial.Delaunay(points)
    neighbours    = collections.defaultdict(set)
    for point in triangulation.vertices:
        for u,v in itertools.combinations(point, 2):
            neighbours[u].add(v)
            neighbours[v].add(u)

    # sample node degrees
    degrees = dict()

    G = networkx.Graph()
    for (u, vs) in neighbours.items():
        for v in vs:
            G.add_edge(u, v)

    return G, points


attacks_per_zone_per_day    = round(1000000000 / 40)
attacks_per_zone_per_hour   = round(attacks_per_zone_per_day / 24)
attacks_per_zone_per_minute = round(attacks_per_zone_per_hour / 60)


@click.command()
@click.argument("num_nodes",        type = int,   default = 40)
@click.argument("outfile",          type = str)
@click.option("--ticks",            type = int,   default = 10 * attacks_per_zone_per_minute)
@click.option("--seed",             type = int,   default = 42)
@click.option("--attack-frequency", type = float, default =  0.0002)
def run(num_nodes, outfile, ticks, seed, attack_frequency):
    numpy.random.seed(seed)

    # generate a network
    G = generate_graph(num_nodes)


if __name__ == '__main__':
    run()
