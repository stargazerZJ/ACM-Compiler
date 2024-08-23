//
// Created by zj on 8/23/2024.
//
#include "dominance_frontier.h"


int main() {
    /* input:
    0 1
    1 2
    2 3
    2 4
    2 5
    3 6
    6 7
    6 9
    6 8
    4 5
    5 7
    6 7
    3 0
    2 5
    4 2
    */
    graph_type graph = {
        {1},
        {2},
        {3, 4, 5},
        {0, 6},
        {2, 5},
        {7},
        {7, 8, 9},
        {}, {}, {}
    };
    auto result = get_reverse_dominance_frontier(graph);
    for (int i = 0; i < result.size(); ++i) {
        std::cout << "Node " << i << ": ";
        for (int j : result[i]) {
            std::cout << j << " ";
        }
        std::cout << std::endl;
    }
    return 0;
}
