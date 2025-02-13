from collections import defaultdict

from mxc.common.ir_repr import IRFunction, IRRet, UnreachableBlock, IRPhi, IRBranch, IRJump, BBExit
from mxc.common.ir_repr import IRBlock


def remove_unreachable(function: IRFunction):
    blocks = function.blocks

    # Step 1: Compute all blocks reachable from the entry, ignoring removed edges
    forward_reachable = set()
    stack = [blocks[0]]
    while stack:
        block = stack.pop()
        if block in forward_reachable:
            continue
        forward_reachable.add(block)
        for succ in block.successors:
            if (block, succ) not in function.edge_to_remove:
                stack.append(succ)

    # Step 2: Compute all blocks that can reach a return, ignoring removed edges
    # Build predecessor map within forward_reachable
    predecessor_map = defaultdict(list)
    for block in forward_reachable:
        for succ in block.successors:
            if (block, succ) not in function.edge_to_remove and succ in forward_reachable:
                predecessor_map[succ].append(block)

    backward_reachable = set()
    return_blocks = [block for block in forward_reachable if isinstance(block.cmds[-1], IRRet)]
    stack = return_blocks.copy()
    while stack:
        block = stack.pop()
        if block in backward_reachable:
            continue
        backward_reachable.add(block)
        for pred in predecessor_map.get(block, []):
            stack.append(pred)

    # Intersection of forward and backward reachable
    reachable = forward_reachable & backward_reachable

    if not reachable:
        function.blocks = [UnreachableBlock]
        return

    new_blocks = []
    for block in blocks:
        if block not in reachable:
            continue
        new_blocks.append(block)
        # Update phi instructions to only include valid predecessors
        for phi in block.cmds:
            if not isinstance(phi, IRPhi):
                break
            valid_entries = [
                (pred, value) for pred, value in zip(phi.sources, phi.var_use)
                if pred in reachable and (pred, block) not in function.edge_to_remove
            ]
            phi.sources = [pred for pred, _ in valid_entries]
            phi.var_use = [value for _, value in valid_entries]
        # Update branch instructions if any edges are removed or lead to unreachable
        last_cmd = block.cmds[-1] if block.cmds else None
        if isinstance(last_cmd, IRBranch):
            valid_successors = []
            for succ in block.successors:
                if succ in reachable and (block, succ) not in function.edge_to_remove:
                    valid_successors.append(succ)
            # Replace with jump if not all successors are valid
            if len(valid_successors) != len(block.successors):
                if valid_successors:
                    target = valid_successors[0]
                    block.successors = [target]
                    block.cmds[-1] = IRJump(BBExit(block, 0))
                else:
                    # This block should have been pruned; handle as needed
                    pass

    # Remove phi instructions with only one source
    rename_map : dict[str, str] = {}
    for block in new_blocks:
        for cmd in block.cmds:
            cmd.var_use = [rename_map.get(var, var) for var in cmd.var_use]
            if isinstance(cmd, IRPhi):
                if len(cmd.sources) == 1:
                    rename_map[cmd.dest] = cmd.var_use[0]

    function.blocks = new_blocks
    function.edge_to_remove.clear()
