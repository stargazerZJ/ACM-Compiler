//
// Created by zj on 8/23/2024.
//

#pragma once

#include <vector>
#include <stack>
#include "dynamic_bitset.h"

using graph_type = std::vector<std::vector<int>>;

inline graph_type reverse_graph(const graph_type &graph) {
    graph_type reversed_graph(graph.size());
    for (int i = 0; i < graph.size(); ++i) {
        for (int j : graph[i]) {
            reversed_graph[j].push_back(i);
        }
    }
    return reversed_graph;
}

inline void dfs(const graph_type& graph, int v, std::vector<bool>& visited, std::stack<int>& stack) {
    visited[v] = true;
    for (int u : graph[v]) {
        if (!visited[u]) {
            dfs(graph, u, visited, stack);
        }
    }
    stack.push(v);
}

inline void assign_scc(const graph_type& reversed_graph, int v, std::vector<int>& scc, int component) {
    scc[v] = component;
    for (int u : reversed_graph[v]) {
        if (scc[u] == -1) {
            assign_scc(reversed_graph, u, scc, component);
        }
    }
}

/**
 * @brief Given a 0-indexed directed graph represented as a reversed adjacency list, returns the indirect predecessor set of each node.
 *      The indirect predecessor set of a node is the set of nodes that can reach the node through a directed path whose length is at least 2.
**/
inline graph_type get_indirect_predecessor_set(const graph_type& reversed_graph) {
    int n = reversed_graph.size();

    // Step 1: Perform Kosaraju's algorithm
    graph_type graph = reverse_graph(reversed_graph);

    std::vector<bool> visited(n, false);
    std::stack<int>   stack;
    for (int i = 0; i < n; ++i) {
        if (!visited[i]) {
            dfs(reversed_graph, i, visited, stack);
        }
    }

    std::vector<int> scc(n, -1);
    int              component = 0;
    while (!stack.empty()) {
        int v = stack.top();
        stack.pop();
        if (scc[v] == -1) {
            assign_scc(graph, v, scc, component++);
        }
    }

    // Step 2: Create a new graph of SCCs
    graph_type                    scc_reversed_graph(component);
    std::vector<std::vector<int>> scc_nodes(component);
    for (int i = 0; i < n; ++i) {
        scc_nodes[scc[i]].push_back(i);
        for (int j : reversed_graph[i]) {
            if (scc[i] != scc[j]) {
                scc_reversed_graph[scc[i]].push_back(scc[j]);
            }
        }
    }

    for (auto& successors : scc_reversed_graph) {
        std::ranges::sort(successors);
        successors.erase(std::ranges::unique(successors).begin(), successors.end());
    }

    // Step 3: Calculate predecessor set for each SCC
    std::vector<dynamic_bitset> scc_predecessors(component, dynamic_bitset(component));
    for (int i = component - 1; i >= 0; --i) {
        scc_predecessors[i].set(i);
        for (int j : scc_reversed_graph[i]) {
            scc_predecessors[i] |= scc_predecessors[j];
        }
    }

    // Step 4 & 5: Calculate indirect predecessor set for each node
    graph_type result(n);
    for (int i = 0; i < component; ++i) {
        std::vector<int> &scc_result = result[scc_nodes[i].front()];
        dynamic_bitset   &predecessors = scc_predecessors[i];

        if (auto& r = reversed_graph[scc_nodes[i][0]];
            scc_nodes[i].size() == 1 &&
            std::ranges::find(r, scc_nodes[i][0]) == r.end()) {
            predecessors.set(i, false);
        }

        for (int scc_id : predecessors.get_ones()) {
            scc_result.insert(scc_result.end(), scc_nodes[scc_id].begin(), scc_nodes[scc_id].end());
        }

        for (int node : scc_nodes[i]) {
            result[node] = scc_result;
        }
    }

    return result;
}
