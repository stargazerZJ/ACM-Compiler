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
}
