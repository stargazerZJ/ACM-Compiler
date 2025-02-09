from mxc.common import dominator

input = [
    [1],
    [2],
    [3, 4, 5],
    [0, 6],
    [2, 5],
    [7],
    [7, 8, 9],
    [],
    [],
    []
]

result = dominator.get_reverse_dominance_frontier(input)

for i, frontier in enumerate(result):
    print(f"Node {i}: {frontier}")