#!/usr/bin/env python3

import click
import numpy
import networkx

def sample_coordinates():
    return (numpy.random.rand(), numpy.random.rand())

def truncated_exponential(rmin = 0, rmax = 2**0.5):
    while True:
        r = numpy.random.exponential(scale = 0.1)
        if rmin <= r < rmax:
            return r

def pick_target(nearest_neighbours):
    (_, rmax) = nearest_neighbours[-1]
    r = truncated_exponential(rmax = rmax)
    ix = 0
    while nearest_neighbours[ix][1] < r:
        ix += 1
    return nearest_neighbours[ix][0]

def generate_graph(num_nodes, num_hubs, ticks, seed, attacker_at_hub, attacker_activity, hub_fixation):
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
    while attacker_at_hub and attacker in hubs:
        attacker = numpy.random.choice(the_nodes)

    # precompute lists of nearest neighbours
    nearest_neighbours = { node : sorted( [ (other, ((nx-ox)**2+(ny-oy)**2)**0.5) for other, (ox,oy) in nodes.items() ]
                                        , key = lambda p: p[1]
                                        )
                             for node, (nx, ny) in nodes.items()
                         }

    graph = dict()
    attacks = list()

    # simulate connections
    for tick in range(ticks):
        # choose a source node
        source = numpy.random.choice(the_nodes)

        # fix on a hub or choose among all nodes
        if numpy.random.rand() < hub_fixation:
            target = pick_target([(n,d) for (n,d) in nearest_neighbours[source] if n in hubs])
        else:
            target = pick_target(nearest_neighbours[source])

        edge = (source, target)

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

    return G, attacks, hubs, attacker


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


@click.command()
@click.argument("num_nodes",         type = int,   default =  40)
@click.argument("num_hubs",          type = int,   default =   3)
@click.option("--ticks",             type = int,   default = 100)
@click.option("--seed",              type = int,   default =  42)
@click.option("--attacker-at-hub",   type = bool,  default = False)
@click.option("--attacker-activity", type = float, default = 0.1)
@click.option("--hub-fixation",      type = float, default = 0.2)
def run(num_nodes, num_hubs, ticks, seed, attacker_at_hub, attacker_activity, hub_fixation):
    G, G_attack, hubs, attacker = generate_graph(num_nodes, num_hubs, ticks, seed, attacker_at_hub, attacker_activity, hub_fixation)

    # overlay the graphs

    # write the graph to stdout
    print(serialise_graph(G, hubs, attacker))

if __name__ == '__main__':
    run()
