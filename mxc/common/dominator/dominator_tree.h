//
// Created by zj on 8/22/2024.
//

#pragma once
#include <vector>
#include <functional>


using graph_type = std::vector<std::vector<int>>;

/// All the public methods assumes 0-indexed graph, while internally it uses 1-indexed graph.
class DominatorTree {
    // source: https://www.luogu.com.cn/article/xzjzyi12
private:
    int num_nodes, edge_count = 0, dfs_count = 0;
    std::vector<std::vector<int>> original_graph, reverse_graph, semi_dominator_tree;
    std::vector<int> dfs_number, dfs_order, parent, immediate_dominator, semi_dominator, disjoint_set, min_vertex,
                     subtree_size;

    int find_set(int v) {
        if (v == disjoint_set[v]) return v;
        int root = find_set(disjoint_set[v]);
        if (dfs_number[semi_dominator[min_vertex[disjoint_set[v]]]] < dfs_number[semi_dominator[min_vertex[v]]])
            min_vertex[v] = min_vertex[disjoint_set[v]];
        return disjoint_set[v] = root;
    }

    void dfs(int v) {
        dfs_order[dfs_number[v] = ++dfs_count] = v;
        for (int u : original_graph[v]) {
            if (!dfs_number[u]) {
                parent[u] = v;
                dfs(u);
            }
        }
    }

    void compute_dominators(int start) {
        dfs(start);
        for (int i            = 1; i <= num_nodes; ++i)
            semi_dominator[i] = disjoint_set[i] = min_vertex[i] = i;

        for (int i = dfs_count; i >= 2; --i) {
            int w = dfs_order[i];
            for (int v : reverse_graph[w]) {
                if (!dfs_number[v]) continue;
                find_set(v);
                if (dfs_number[semi_dominator[min_vertex[v]]] < dfs_number[semi_dominator[w]])
                    semi_dominator[w] = semi_dominator[min_vertex[v]];
            }
            disjoint_set[w] = parent[w];
            semi_dominator_tree[semi_dominator[w]].push_back(w);

            for (int v : semi_dominator_tree[w = parent[w]]) {
                find_set(v);
                immediate_dominator[v] = (w == semi_dominator[min_vertex[v]]) ? w : min_vertex[v];
            }
            semi_dominator_tree[w].clear();
        }

        for (int i = 2; i <= dfs_count; ++i) {
            int w = dfs_order[i];
            if (immediate_dominator[w] != semi_dominator[w])
                immediate_dominator[w] = immediate_dominator[immediate_dominator[w]];
        }
    }

    std::vector<int> compute_dominated_node_counts() {
        std::vector<int> subtree_size(num_nodes + 1);
        for (int i = dfs_count; i >= 2; --i)
            subtree_size[immediate_dominator[dfs_order[i]]] += ++subtree_size[dfs_order[i]];
        ++subtree_size[1];
        return subtree_size;
    }

public:
    /**
     * @brief Constructor to initialize the DominatorTree with a given number of nodes.
     * @details This constructor initializes all internal data structures required for the algorithm.
     * @param n The number of nodes in the graph.
     */
    explicit DominatorTree(int n) : num_nodes(n) {
        original_graph.resize(n + 1);
        reverse_graph.resize(n + 1);
        semi_dominator_tree.resize(n + 1);
        dfs_number.resize(n + 1);
        dfs_order.resize(n + 1);
        parent.resize(n + 1);
        immediate_dominator.resize(n + 1);
        semi_dominator.resize(n + 1);
        disjoint_set.resize(n + 1);
        min_vertex.resize(n + 1);
    }

    /**
     * @brief Constructor to initialize the DominatorTree with a given graph.
     * @details This constructor takes a 0-indexed graph and converts it into the internal 1-indexed representation.
     * @param graph The 0-indexed adjacency list of the graph.
     */
    explicit DominatorTree(const std::vector<std::vector<int>>& graph) : DominatorTree(graph.size()) {
        for (int i = 0; i < num_nodes; ++i) {
            for (int j : graph[i]) {
                add_edge(i, j);
            }
        }
    }

    /**
     * @brief Adds an edge to the graph.
     * @details Converts the provided 0-indexed edge to a 1-indexed edge for internal storage.
     * @param from The starting node of the edge (0-indexed).
     * @param to The ending node of the edge (0-indexed).
     */
    void add_edge(int from, int to) {
        from++;
        to++; // Convert to 1-indexed graph.
        original_graph[from].push_back(to);
        reverse_graph[to].push_back(from);
    }

    void compute(int start = 0) {
        compute_dominators(start + 1);
    }

    /**
     * @brief Computes and returns the number of nodes each node dominates starting from a specified node.
     * @details This function computes dominators beginning from the provided start node and calculates the number of nodes dominated by each node.
     * @param start The node from which to start the computation (0-indexed). Defaults to 0.
     * @return A vector containing the number of nodes each node dominates.
     */
    std::vector<int> get_dominated_node_counts() {
        return compute_dominated_node_counts();
    }

    /**
     * @brief Computes and returns the immediate dominators of each node starting from a specified node.
     * @details This function computes the immediate dominators beginning from the provided start node and returns them in a 0-indexed format.
     * @param start The node from which to start the computation (0-indexed). Defaults to 0.
     * @return A 0-indexed vector containing the immediate dominators of each node.
     */
    std::vector<int> get_immediate_dominators() {
        std::vector<int> idom_0_ind(num_nodes);
        for (int i = 1; i <= num_nodes; ++i) {
            idom_0_ind[i - 1] = immediate_dominator[i] - 1;
        }
        return idom_0_ind;
    }

    std::vector<int> get_dfs_order() {
        std::vector<int> dfs_0_ind(num_nodes);
        for (int i = 1; i <= num_nodes; ++i) {
            dfs_0_ind[i - 1] = dfs_order[i] - 1;
        }
        return dfs_0_ind;
    }
};

/**
 * @brief Computes the DFS order of the dominator tree for the given graph.
 * @details This function computes the dominator tree from the given graph and performs a DFS on the dominator tree to return the DFS order.
 * @param graph The 0-indexed adjacency list of the graph.
 * @return A vector containing the DFS order of the dominator tree nodes.
 */
inline std::vector<int> get_dominator_tree_dfs_order(const graph_type& graph) {
    DominatorTree dt(graph);
    dt.compute();
    auto idom = dt.get_immediate_dominators();

    // Create the dominator tree from the immediate dominators
    graph_type dominator_tree(graph.size());
    for (int i = 0; i < idom.size(); ++i) {
        if (idom[i] != -1) {
            dominator_tree[idom[i]].push_back(i);
        }
    }

    // Perform DFS on the dominator tree to get the DFS order
    std::vector<int>  dfs_order;
    std::vector<bool> visited(graph.size(), false);
    dfs_order.reserve(graph.size());

    std::function<void(int)> dfs = [&](int node) {
        visited[node] = true;
        dfs_order.push_back(node);
        for (int neighbor : dominator_tree[node]) {
            if (!visited[neighbor]) {
                dfs(neighbor);
            }
        }
    };

    dfs(0);

    return dfs_order;
}
