#!/usr/bin/env python3

import collections
import click
import json
import multiprocessing
import numpy
import networkx
import random


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


def generate_graph(num_nodes, num_hubs, ticks, seed, attacker_at_hub, attacker_activity, hub_to_hub_probability, hub_fixation):
    numpy.random.seed(seed)

    # sample node positions in the unit square
    nodes = { node : sample_coordinates()
                for node in range(1, num_nodes+1)
            }

    the_nodes = list(nodes.keys())

    # choose the hubs
    hubs = numpy.random.choice(the_nodes, size = num_hubs, replace = False)

    # choose an attacker, perhaps make sure it's not a hub
    attacker = numpy.random.choice(the_nodes)
    while not attacker_at_hub and attacker in hubs:
        attacker = numpy.random.choice(the_nodes)

    # precompute lists of nearest neighbours
    nearest_neighbours = { node : sorted( [ (other, ((nx-ox)**2+(ny-oy)**2)**0.5) for other, (ox,oy) in nodes.items() ]
                                        , key = lambda p: p[1]
                                        )
                             for node, (nx, ny) in nodes.items()
                         }
    # trim lists of nearest neighbours
    # nearest_neighbours = {}
    # for key, value in nearest_neighbours_untrimmed.items():
    #     if key in hubs:
    #         nearest_neighbours[key] = value[:15+random.randint(0,10)]
    #     else:
    #         nearest_neighbours[key] = value[:5+random.randint(0,5)]

    # training data
    # the connections that will be in the graph
    graph   = dict()

    # validation data
    # good connections and attacks that we don't put into the graph
    extra   = list()
    attacks = list()

    # simulate connections
    for tick in range(ticks):
        # choose a source node
        source = numpy.random.choice(the_nodes)

        # hubs like to connect to each other
        if source in hubs:
            if numpy.random.rand() < hub_to_hub_probability:
                target = pick_target([(n,d) for (n,d) in nearest_neighbours[source] if n in hubs])
            else:
                target = pick_target(nearest_neighbours[source][:15+random.randint(0,10)])

        # normal nodes: fix on a hub or choose among all nodes
        elif numpy.random.rand() < hub_fixation:
            target = pick_target([(n,d) for (n,d) in nearest_neighbours[source] if n in hubs])
        else:
            target = pick_target(nearest_neighbours[source][:5+random.randint(0,5)])

        edge = (source, target)

        # use 10% of the data as validation data
        if tick % 10 == 0:
            extra.append(edge)
        # the other 90% as training data
        else:
            if edge not in graph:
                graph[edge] = 0
            graph[edge] += 1

        # run an attack, choose a target node uniformly at random
        if numpy.random.rand() < attacker_activity:
            target = numpy.random.choice(the_nodes)
            while target == attacker:
                target = numpy.random.choice(the_nodes)

            # an attack means that a user moves from some other node to the
            # attacker node, not the other way around!
            # but we still call the attacked node the target
            attacks.append((target, attacker))

    G = networkx.DiGraph()
    for node, (x,y) in nodes.items():
        G.add_node(node, x = x, y = y)
    for (u,v),w in graph.items():
        G.add_edge(u, v, weight = w)

    return G, extra, attacks, hubs, attacker


def do_random_walk(transition_probabilities, source, target):
    steps = 0
    while source != target and steps < 10000:
        neigbours = list(transition_probabilities[source].items())
        source = numpy.random.choice( a    = [n for (n,_) in neigbours]
                                    , size = 1
                                    , p    = [p for (_,p) in neigbours]
                                    )[0]
        steps += 1
    return steps


def getMedian(sourceTarget):
    source, target = sourceTarget
    return ( source
           , target
           , numpy.median([do_random_walk(transition_probabilities, source, target) for _ in range(100)])
           )


def serialise_graph(G, hubs, attacker):
    res = []

    hubs_string = ",".join([str(hub) for hub in hubs])
    res.append(f"# hubs: [{hubs_string}], attacker: {attacker}")

    res.append(f"*Vertices {len(G.nodes)}")
    for node in sorted(G.nodes):
        res.append(f"{node} \"{node}\"")

    res.append(f"*Edges {len(G.edges)}")
    for (u,v) in G.edges:
        w = G.edges[(u,v)]["weight"]
        res.append(f"{u} {v} {w}")

    return "\n".join(res)


attacks_per_zone_per_day    = round(1000000000 / 40)
attacks_per_zone_per_hour   = round(attacks_per_zone_per_day / 24)
attacks_per_zone_per_minute = round(attacks_per_zone_per_hour / 60)


@click.command()
@click.argument("num_nodes",              type = int,   default =  40)
@click.argument("num_hubs",               type = int,   default =   3)
@click.argument("outfile",                type = str)
@click.option("--ticks",                  type = int,   default =  10 * attacks_per_zone_per_minute)
@click.option("--seed",                   type = int,   default =  42)
@click.option("--attacker-at-hub",        type = bool,  default = False)
@click.option("--attacker-activity",      type = float, default =   0.0002)
@click.option("--hub-to-hub-probability", type = float, default =   0.35)
@click.option("--hub-fixation",           type = float, default =   0.0)
def run(num_nodes, num_hubs, outfile, ticks, seed, attacker_at_hub, attacker_activity, hub_to_hub_probability, hub_fixation):
    # generate a network
    G, extra, attacks, hubs, attacker = \
        generate_graph( num_nodes              = num_nodes
                      , num_hubs               = num_hubs
                      , ticks                  = ticks
                      , seed                   = seed
                      , attacker_at_hub        = attacker_at_hub
                      , attacker_activity      = attacker_activity
                      , hub_to_hub_probability = hub_to_hub_probability
                      , hub_fixation           = hub_fixation
                      )

    # add half of the attacks to the graph so the training data is not too clean
    for (source, target) in attacks[:len(attacks)//2]:
        w = 1
        if (source, target) in G.edges:
            w += G.edges[(source, target)]["weight"]
        G.add_edge(source, target, weight = w)

    # keep the other half for detection later
    kept_attacks = attacks[len(attacks)//2:]

    # calculate the transition probabilities between nodes for the random walk
    transition_probabilities = dict()

    for s in G.nodes:
        transition_probabilities[s] = collections.defaultdict(float)
        w_total = 0
        for t in G.neighbors(s):
            w_total += G.edges[(s,t)]["weight"]
        for t in G.neighbors(s):
            transition_probabilities[s][t] = G.edges[(s,t)]["weight"] / w_total

    # estimate the median number of steps from source to target nodes that a
    # random walk needs
    median_steps_connected    = dict()
    median_steps_disconnected = dict()

    # median number of steps for connected nodes
    pairs = list(G.edges)
    with multiprocessing.Pool() as p:
        medians = p.map(getMedian, pairs)

    for source, target, steps in medians:
        median_steps_connected[(source, target)] = steps

    # median number of steps for disconnected nodes (new valid connections + attacks)
    pairs = set(kept_attacks + extra).difference(set(G.edges))
    with multiprocessing.Pool() as p:
        attack_medians = p.map(getMedian, pairs)

    for source, target, steps in attack_medians:
        median_steps_disconnected[(source, target)] = steps

    # find the threshold to separate attacks from non-attacks
    l = list(median_steps_connected.values())
    threshold = sorted(l)[:round(0.95*len(l))][-1]

    # check the "good" edges, that is the non-attacks
    tn = 0
    fp = 0

    for (source, target) in extra:
        if (source, target) in G.edges:
            steps = median_steps_connected[(source, target)]
        else:
            steps = median_steps_disconnected[(source, target)]

        if steps > threshold:
            fp += 1
        else:
            tn += 1

    # now check the attacks
    tp = 0
    fn = 0

    median_steps_attack = list()

    for (target, attacker) in kept_attacks:
        if (target, attacker) in G.edges:
            steps = median_steps_connected[(target, attacker)]
        else:
            steps = median_steps_disconnected[(target, attacker)]
        median_steps_attack.append(steps)

        if steps > threshold:
            tp += 1
        else:
            fn += 1

    result = { num_nodes              : num_nodes
             , num_hubs               : num_hubs
             , ticks                  : ticks
             , seed                   : seed
             , attacker_at_hub        : attacker_at_hub
             , attacker_activity      : attacker_activity
             , hub_to_hub_probability : hub_to_hub_probability
             , hub_fixation           : hub_fixation
             , tp                     : tp
             , tn                     : tn
             , fp                     : fp
             , fn                     : fn
             , recall                 : tp / (tp + fn)
             , precision              : tp / (tp + fp)
             , f1                     : tp / (tp + 0.5 * (fp + fn))
             }

    with open(outfile, "w") as fh:
        json.dumps(fh)


if __name__ == '__main__':
    run()
