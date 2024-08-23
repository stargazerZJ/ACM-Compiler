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
}
