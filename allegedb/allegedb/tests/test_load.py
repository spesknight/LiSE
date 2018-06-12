import pytest
import os
from allegedb import ORM
import networkx as nx


scalefreestart = nx.MultiDiGraph(name='scale_free_graph_2')
scalefreestart.add_edges_from([(0, 1), (1, 2), (2, 0)])


testgraphs = [
    nx.chvatal_graph(create_using=nx.Graph(name='chvatal_graph')),
    nx.scale_free_graph(2, create_using=scalefreestart),
    nx.chordal_cycle_graph(2, create_using=nx.MultiGraph(name='chordal_cycle_graph_2')),
    nx.path_graph(9, create_using=nx.DiGraph(name='path_graph_9'))
]


@pytest.fixture
def db():
    name = 'allegedb_load_test.db'
    if os.path.exists(name):
        os.remove(name)
    with ORM('sqlite:///' + name) as orm:
        for graph in testgraphs:
            {
                nx.Graph: orm.new_graph,
                nx.DiGraph: orm.new_digraph,
                nx.MultiGraph: orm.new_multigraph,
                nx.MultiDiGraph: orm.new_multidigraph
            }[type(graph)](graph.name, graph)
    with ORM('sqlite:///' + name) as orm:
        yield orm
    os.remove(name)


def test_basic_load(db):
    for graph in testgraphs:
        alleged = db.graph[graph.name]
        assert set(graph.node.keys()) == set(alleged.node.keys()), "{}'s nodes are not the same after load".format(
            graph.name
        )
        assert set(graph.edges) == set(alleged.edges), "{}'s edges are not the same after load".format(graph.name)