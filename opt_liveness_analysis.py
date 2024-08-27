from ir_repr import BasicBlock, IRFunction, IRPhi
from opt_utils import mark_blocks


def collect_defs(blocks: list[BasicBlock]):
    return {var
            for block in blocks
            for cmd in block
            for var in cmd.var_def}

def collect_uses(defs: set[str], blocks: list[BasicBlock]) -> dict[str, list[tuple[BasicBlock, int]]]:
    use_sites = {def_ : [] for def_ in defs}
    for block in blocks:
        for cmd_ind, cmd in enumerate(block.cmds):
            for use in cmd.var_use:
                if use in defs:
                    use_sites[use].append((block, cmd_ind))
    return use_sites

def init_live_out(blocks: list[BasicBlock]):
    for block in blocks:
        for cmd in block.cmds:
            cmd.live_out = set()

def liveness_analysis(function: IRFunction):
    blocks: list[BasicBlock] = function.blocks

    mark_blocks(blocks)
    defs = collect_defs(blocks)
    use_sites = collect_uses(defs, blocks)
    init_live_out(blocks)
    function.var_defs = defs

    def scan_block(block:BasicBlock):
        if block in visited: return
        visited.add(block)
        for cmd in block.cmds[::-1]:
            cmd.live_out.add(var)
            if var in cmd.var_def:
                return
        for pred in block.predecessors:
            scan_block(pred.block)

    def scan_live_in(block:BasicBlock, cmd_ind: int):
        for cmd in block.cmds[:cmd_ind][::-1]:
            if var in cmd.live_out:
                return
            cmd.live_out.add(var)
            if var in cmd.var_def:
                return
        for pred in block.predecessors:
            scan_block(pred.block)

    visited: set[BasicBlock] = set()
    for var, uses in use_sites.items():
        visited.clear()
        for use in uses:
            cmd = use[0].cmds[use[1]]
            if isinstance(cmd, IRPhi):
                for var_use, source in zip(cmd.var_use, cmd.sources):
                    if var_use == var:
                        scan_block(source)
            else:
                scan_live_in(*use)