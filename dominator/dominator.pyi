# dominator.pyi

from typing import List

# Aliases for readability
graph_type = List[List[int]]

def get_reverse_dominance_frontier(graph: graph_type) -> graph_type:
    """
    Get the reverse dominance frontier mapping of every node in a directed graph.
    If result[x] contains y, then node x is in the dominance frontier of node y.

    :param graph: The directed graph represented as an adjacency list.
    :return: The reverse dominance frontier mapping as a graph_type.
    """
    pass

def get_indirect_predecessor_set(reversed_graph: graph_type) -> graph_type:
    """
    Given a 0-indexed directed graph represented as a reversed adjacency list,
    returns the indirect predecessor set of each node.
    The indirect predecessor set of a node is the set of nodes that can reach
    the node through a directed path whose length is at least 2.

    :param reversed_graph: The reversed adjacency list of the directed graph.
    :return: The indirect predecessor set as a graph_type.
    """
    pass

def get_indirect_predecessor_set_of_dominator_frontier(graph: graph_type) -> graph_type:
    """
    Get the indirect predecessor set of the dominator frontier of each node in
    a directed graph.

    :param graph: The directed graph represented as an adjacency list.
    :return: The indirect predecessor set of the dominator frontier as a graph_type.
    """
    pass
