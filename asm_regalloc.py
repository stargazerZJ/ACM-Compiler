import dominator
from ir_repr import IRFunction, IRPhi
from opt_utils import build_graph

K = 26 # ra, a0-a7, s0-s11, t2-t6

class AllocationBase:
    pass

class AllocationStack(AllocationBase):
    pointer_name: str
    def __init__(self, pointer_name: str):
        self.pointer_name = pointer_name

class AllocationRegister(AllocationBase):
    logical_id: int
    id: int
    def __init__(self, logical_id: int):
        self.logical_id = logical_id

def get_pointer_name(var: str):
    # "abc.val.1"       -> "abc.ptr"
    # "abc.val"         -> "abc.ptr"
    # "abc.val.a.val.2" -> "abc.val.a.ptr"
    # "abc"             -> "abc.ptr"
    return var.rsplit(".val", 1)[0] + ".ptr"

def choose_spill(vars_: set[str], unassigned: set[str], allocation_table: dict[str, AllocationBase]):
    n = K - len(vars_)
    for _ in range(n):
        var = vars_.pop()
        spill_to_stack(var, unassigned, allocation_table)


def spill_to_stack(var, unassigned, allocation_table):
    pointer_name = get_pointer_name(var)
    unassigned.remove(var)
    allocation_table[var] = AllocationStack(pointer_name)


def spill(function: IRFunction):
    unassigned = function.var_defs.copy()
    allocation_table: dict[str, AllocationBase] = {}
    for block in function.blocks:
        for cmd in block.cmds:
            vars_ = unassigned.intersection(cmd.live_out)
            if len(vars_) > K:
                choose_spill(vars_, unassigned, allocation_table)
            for var in cmd.var_def:
                if var not in cmd.live_out:
                    # Temporary solution: if a variable is never used, spill it to stack to avoid error
                    # this problem will resolve after we implement dead code elimination
                    spill_to_stack(var, unassigned, allocation_table)
    # function.unassigned = unassigned
    # function.allocation_table = allocation_table
    return unassigned, allocation_table

def allocate_registers(function: IRFunction):
    blocks = function.blocks

    cfg = build_graph(blocks)
    dfs_order = dominator.get_dominator_tree_dfs_order(cfg)

    unassigned, allocation_table = spill(function)

    # in_use: set[int] = set()
    vacant: set[int] = set(range(K))
    for ind in dfs_order:
        block = blocks[ind]
        for var in block.live_in:
            if var in allocation_table:
                reg = allocation_table[var]
                if isinstance(reg, AllocationRegister):
                    vacant.discard(reg.logical_id)

        for cmd in block.cmds:
            if not isinstance(cmd, IRPhi):
                break
            for var in cmd.var_use:
                if var in allocation_table and var not in cmd.live_out:
                    reg = allocation_table[var]
                    if isinstance(reg, AllocationRegister):
                        vacant.add(reg.logical_id)

        for cmd in block.cmds:
            if not isinstance(cmd, IRPhi):
                for var in cmd.var_use:
                    if var in allocation_table and var not in cmd.live_out:
                        reg = allocation_table[var]
                        if isinstance(reg, AllocationRegister):
                            vacant.add(reg.logical_id)
            for var in cmd.var_def:
                if var in unassigned:
                    reg_id = min(vacant)
                    vacant.remove(reg_id)
                    unassigned.remove(var)
                    allocation_table[var] = AllocationRegister(reg_id)

    function.allocation_table = allocation_table