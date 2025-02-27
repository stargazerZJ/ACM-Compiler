from mxc.common.ir_repr import IRBlock, IRFunction, IRPhi
from .utils import mark_blocks, collect_defs, collect_uses


def init_live_out(blocks: list[IRBlock]):
    for block in blocks:
        for cmd in block.cmds:
            cmd.live_out = set()


def liveness_analysis(function: IRFunction):
    blocks: list[IRBlock] = function.blocks

    mark_blocks(blocks)
    defs = collect_defs(function)
    defs.add("ret_addr")
    defs.update({
        param + ".param" for param in function.info.param_ir_names
    })
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
            scan_block(pred)

    def scan_live_in(block: IRBlock, cmd_ind: int):
        for cmd in block.cmds[:cmd_ind][::-1]:
            if var in cmd.live_out:
                return
            cmd.live_out.add(var)
            if var in cmd.var_def:
                return
        block.live_in.add(var)
        for pred in block.predecessors:
            scan_block(pred)

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
