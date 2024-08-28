from ir_repr import IRBlock, IRFunction, IRPhi
from opt_utils import mark_blocks


def collect_defs(function: IRFunction) -> set[str]:
    blocks = function.blocks
    defs = {var
            for block in blocks
            for cmd in block
            for var in cmd.var_def}
    defs.add("ret_addr")
    defs.union({
        param + ".param" for param in function.info.param_ir_names
    })
    return defs


def collect_uses(defs: set[str], blocks: list[IRBlock]) -> dict[str, list[tuple[IRBlock, int]]]:
    use_sites = {def_: [] for def_ in defs}
    for block in blocks:
        for cmd_ind, cmd in enumerate(block.cmds):
            for use in cmd.var_use:
                if use in defs:
                    use_sites[use].append((block, cmd_ind))
    return use_sites


def init_live_out(blocks: list[IRBlock]):
    for block in blocks:
        for cmd in block.cmds:
            cmd.live_out = set()


def liveness_analysis(function: IRFunction):
    blocks: list[IRBlock] = function.blocks

    mark_blocks(blocks)
    defs = collect_defs(function)
    use_sites = collect_uses(defs, blocks)
    init_live_out(blocks)
    function.var_defs = defs

    def scan_block(block: IRBlock):
        if block in visited: return
        visited.add(block)
        for cmd in block.cmds[::-1]:
            cmd.live_out.add(var)
            if var in cmd.var_def:
                return
        block.live_in.add(var)
        for pred in block.predecessors:
            scan_block(pred.block)

    def scan_live_in(block: IRBlock, cmd_ind: int):
        for cmd in block.cmds[:cmd_ind][::-1]:
            if var in cmd.live_out:
                return
            cmd.live_out.add(var)
            if var in cmd.var_def:
                return
        block.live_in.add(var)
        for pred in block.predecessors:
            scan_block(pred.block)

    visited: set[IRBlock] = set()
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
