#pragma once
#include <vector>
#include <algorithm>
#include "dynamic_bitset.h"
#include "dominator_tree.h"
#include "predecessor_set.h"
/**
 * @brief Get the reverse dominance frontier mapping of every node in a directed graph.
 *      If result[x] contains y, then node x is in the dominance frontier of node y.
 * @details reverse dominance frontier is calculated by $ \bigcup_{m \in preds(n)} \left( Dom(m) - (Dom(n) - \{n\}) \right) $
**/
inline graph_type get_reverse_dominance_frontier(const graph_type& graph) {
    int        n = graph.size();
    graph_type result(n);

    // Step 1: Build the reverse graph
    graph_type reverse_graph(n);
    for (int i = 0; i < n; ++i) {
        for (int j : graph[i]) {
            reverse_graph[j].push_back(i);
        }
    }

    // Step 2: Calculate immediate dominators
    DominatorTree domTree(graph);
    domTree.compute();
    std::vector<int> idom      = domTree.get_immediate_dominators();
    std::vector<int> dfs_order = domTree.get_dfs_order();

    // Step 3: Calculate the dominance set of each node using dynamic_bitset
    std::vector<dynamic_bitset> dom_set(n, dynamic_bitset(n));
    for (int i = 0; i < n; ++i) {
        int node = dfs_order[i];
        if (idom[node] != -1) {
             dom_set[node] = dom_set[idom[node]];
        }
        dom_set[node].set(node);
    }

    // Step 4: Calculate the reverse dominance frontier
    for (int node = 0; node < n; ++node) {
        dynamic_bitset fro(n);

        for (int prev : reverse_graph[node]) {
            fro |= dom_set[prev];
        }

        auto tmp = dom_set[node];
        tmp.set(node, false).flip();
        fro &= tmp;

        result[node] = fro.get_ones();
    }

    return result;
}

inline graph_type get_indirect_predecessor_set_of_dominator_frontier(const graph_type& graph) {
    auto reverse_dominance_frontier = get_reverse_dominance_frontier(graph);
    return get_indirect_predecessor_set(reverse_dominance_frontier);
}