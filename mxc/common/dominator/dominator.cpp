//
// Created by zj on 8/23/2024.
//
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "dominance_frontier.h"

namespace py = pybind11;

PYBIND11_MODULE(dominator, m) {
    m.def("get_reverse_dominance_frontier", &get_reverse_dominance_frontier,
          "Get the reverse dominance frontier mapping of every node in a directed graph.");
    m.def("get_indirect_predecessor_set", &get_indirect_predecessor_set,"Given a 0-indexed directed graph represented as a reversed adjacency list, returns the indirect predecessor set of each node\nThe indirect predecessor set of a node is the set of nodes that can reach the node through a directed path whose length is at least 2.");
    m.def("get_indirect_predecessor_set_of_dominator_frontier", &get_indirect_predecessor_set_of_dominator_frontier, "Get the indirect predecessor set of the dominator frontier of each node in a directed graph.");
    m.def("get_dominator_tree_dfs_order", &get_dominator_tree_dfs_order, "Computes the DFS order of the dominator tree for the given graph.");
    py::class_<DominatorTree>(m, "DominatorTree")
        .def(py::init<const graph_type&>())
        .def("compute", &DominatorTree::compute, "Computes the dominator tree.", py::arg("start") = 0)
        .def("get_dominated_node_counts", &DominatorTree::get_dominated_node_counts, "Computes and returns the number of nodes each node dominates starting from a specified node.")
        .def("get_immediate_dominators", &DominatorTree::get_immediate_dominators, "Computes and returns the immediate dominators of each node starting from a specified node.")
        .def("get_dfs_order", &DominatorTree::get_dfs_order, "Computes and returns the DFS order of the original graph.")
        .def("get_dominator_tree_dfs_order", &DominatorTree::get_dominator_tree_dfs_order, "Computes the DFS order of the dominator tree for the given graph.");
}
