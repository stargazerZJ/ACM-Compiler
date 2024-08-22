#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <algorithm>
#include "dynamic_bitset.h"
#include "dominator_tree.h"

/**
 * @brief Get the reverse dominance frontier mapping of every node in a directed graph.
 *      If result[x] contains y, then node x is in the dominance frontier of node y.
 * @details reverse dominance frontier is calculated by $ \bigcup_{m \in preds(n)} \left( Dom(m) - (Dom(n) - \{n\}) \right) $
**/
std::vector<std::vector<int>> get_reverse_dominance_frontier(const std::vector<std::vector<int>>& graph) {
    int n = graph.size();
    std::vector<std::vector<int>> result(n);

    // Step 1: Build the reverse graph
    std::vector<std::vector<int>> reverse_graph(n);
    for (int i = 0; i < n; ++i) {
        for (int j : graph[i]) {
            reverse_graph[j].push_back(i);
        }
    }

    // Step 2: Calculate immediate dominators and build the dominance tree
    DominatorTree domTree(reverse_graph);
    domTree.compute();
    std::vector<int> idom = domTree.get_immediate_dominators();
    std::vector<int> dfs_order = domTree.get_dfs_order();

    // Step 3: Calculate the dominance set of each node using dynamic_bitset
    std::vector<dynamic_bitset> dom_set(n, dynamic_bitset(n));
    for (int i = n - 1; i >= 0; --i) {
        int node = dfs_order[i];
        dom_set[node].set(node);
        if (idom[node] != -1) {
            dom_set[node] |= dom_set[idom[node]];
        }
    }

    // Step 4: Calculate the reverse dominance frontier
    for (int node = 0; node < n; ++node) {
        bool flag = false;
        dynamic_bitset fro(n);

        for (int prev : reverse_graph[node]) {
            flag |= dom_set[prev][node];
            dynamic_bitset tmp = dom_set[prev];
            tmp &= dom_set[node];
            tmp ^= dom_set[prev];
            fro |= tmp;
        }

        fro.set(node, flag);

        std::vector<int> ones = fro.get_ones();
        for (int x : ones) {
            result[x].push_back(node);
        }
    }

    return result;
}


namespace py = pybind11;

PYBIND11_MODULE(dominator, m) {
    m.def("get_reverse_dominance_frontier", &get_reverse_dominance_frontier,
          "Get the reverse dominance frontier mapping of every node in a directed graph.");
}
