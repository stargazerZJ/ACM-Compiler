from mxc.common import dominator
from mxc.common.ir_repr import IRFunction, IRPhi
from mxc.middle_end.utils import build_control_flow_graph

K = 26  # ra, a0-a7, s0-s11, t2-t6
# K = 1   # for debugging, spill everything to stack


class AllocationBase:
    pass


class AllocationStack(AllocationBase):
    pointer_name: str
    offset: int

    def __init__(self, pointer_name: str):
        self.pointer_name = pointer_name

    def __repr__(self):
        return f"Allocated on stack    @{self.offset: <5}, pointer_name: {self.pointer_name}"


class AllocationRegister(AllocationBase):
    logical_id: int
    reg: str

    def __init__(self, logical_id: int):
        self.logical_id = logical_id

    def __repr__(self):
        return f"Allocated on register {self.reg: <5}"


class AllocationGlobal(AllocationBase):
    label: str

    def __init__(self, label: str):
        self.label = label

    def __repr__(self):
        return f"Allocated on global   {self.label}"


def get_pointer_name(var: str):
    # "abc.val.1"       -> "abc.ptr"
    # "abc.val"         -> "abc.ptr"
    # "abc.val.a.val.2" -> "abc.val.a.ptr"
    # "abc"             -> "abc.ptr"
    return var.rsplit(".val", 1)[0] + ".ptr"


def choose_spill(vars_: set[str], unassigned: set[str], allocation_table: dict[str, AllocationBase], k: int = K):
    n = len(vars_) - k
    for _ in range(n):
        # var = vars_.pop()
        var = min(vars_)
        vars_.remove(var)
        spill_to_stack(var, unassigned, allocation_table)


def spill_to_stack(var, unassigned, allocation_table):
    pointer_name = get_pointer_name(var)
    unassigned.remove(var)
    allocation_table[var] = AllocationStack(pointer_name)


def get_short_lived_vars(function: IRFunction):
    """Get variables that are only used in the next instruction after definition"""
    short_lived_vars = set()
    for block in function.blocks:
        for i in range(len(block.cmds) - 1):
            cmd = block.cmds[i]
            next_cmd = block.cmds[i + 1]
            for var in cmd.var_def:
                if var not in next_cmd.live_out:
                    short_lived_vars.add(var)
    return short_lived_vars


def spill(function: IRFunction):
    unassigned = function.var_defs.copy()
    allocation_table: dict[str, AllocationBase] = {}
    short_lived_vars = get_short_lived_vars(function)
    if not function.is_leaf:
        spill_to_stack("ret_addr", unassigned, allocation_table)
    for block in function.blocks:
        for cmd in block.cmds:
            vars_ = unassigned.intersection(cmd.live_out)
            if len(vars_) > K:
                intersection = vars_.intersection(short_lived_vars)
                # intersection = set()
                vars_ -= intersection
                choose_spill(vars_, unassigned, allocation_table, K - len(intersection))
    vars_ = unassigned.intersection(function.blocks[0].live_in)
    if len(vars_) > K:
        choose_spill(vars_, unassigned, allocation_table)
    return unassigned, allocation_table


def allocate_registers(function: IRFunction):
    blocks = function.blocks

    cfg = build_control_flow_graph(blocks)
    dfs_order = dominator.get_dominator_tree_dfs_order(cfg)

    unassigned, allocation_table = spill(function)

    # in_use: set[int] = set()
    vacant: set[int] = set(range(K))

    def allocate(var):
        if var in unassigned:
            reg_id = min(vacant)
            vacant.remove(reg_id)
            unassigned.remove(var)
            allocation_table[var] = AllocationRegister(reg_id)

    allocate("ret_addr")
    for param in function.info.param_ir_names:
        if param + ".param" in function.blocks[0].live_in:
            allocate(param + ".param")
        else:
            # spill unused param to stack (temporary, will be resolved after global DCE)
            # spill_to_stack(param + ".param", unassigned, allocation_table)
            allocate(param + ".param")  # WRONG if there is > K unused params

    for ind in dfs_order:
        vacant = set(range(K))
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
                allocate(var)

    function.allocation_table = allocation_table
    return allocation_table
