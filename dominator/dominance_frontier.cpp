#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include "dynamic_bitset.h"

/// Get the dominance frontier of every node in a directed graph
std::vector<std::vector<int>> get_dominance_frontier(const std::vector<std::vector<int>>& graph) {
    std::vector<std::vector<int>> result(graph.size());

    return result;
}

namespace py = pybind11;

PYBIND11_MODULE(dominator, m) {
    m.def("get_dominance_frontier", &get_dominance_frontier, "Get the dominance frontier of every node in a directed graph");
}