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


def get_dominator_tree_dfs_order(graph: graph_type) -> list[int]:
    """
    Computes the DFS order of the dominator tree for the given graph.
    This function computes the dominator tree from the given graph and performs a DFS on the dominator tree to return the DFS order.

    :param graph: The 0-indexed adjacency list of the graph.
    :return: A vector containing the DFS order of the dominator tree nodes.
    """

class DominatorTree:
    def __init__(self, graph: graph_type):
        """
        Construct the dominator tree from a directed graph.

        :param graph: The directed graph represented as an adjacency list.
        """
        pass

    def compute(self, start_node: int = 0):
        """
        Computes the dominator tree starting from a specified node.

        :param start_node: The node to start the computation from.
        """
        pass

    def get_dominated_node_counts(self) -> List[int]:
        """
        Computes and returns the number of nodes each node dominates starting from a specified node.

        :return: A vector containing the number of nodes each node dominates.
        """
        pass

    def get_immediate_dominators(self) -> List[int]:
        """
        Computes and returns the immediate dominators of each node starting from a specified node.

        :return: A vector containing the immediate dominator of each node.
        """
        pass

    def get_dfs_order(self) -> List[int]:
        """
        Computes and returns the DFS order of the original graph.

        :return: A vector containing the DFS order of the original graph.
        """
        pass

    def get_dominator_tree_dfs_order(self) -> List[int]:
        """
        Computes and returns the DFS order of the dominator tree.

        :return: A vector containing the DFS order of the dominator tree.
        """
        pass

