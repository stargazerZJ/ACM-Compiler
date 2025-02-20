from mxc.common.renamer import renamer
from mxc.common.ir_repr import IRFunction, IRLoad, IRStore, IRRet, IRAlloca


def get_variables_to_inline(function: IRFunction) -> tuple[list[str], list[str], dict[str, str]]:
    """
    Get the global variables that are frequently used in the function

    Currently, only leaf functions are considered
    A maximum of 8 global variables are considered
    """

    if not function.is_leaf:
        return [], [], {}

    global_var_count, stored_global_vars, global_var_types = get_global_variables(function)

    K = 8
    chosen_global_vars = sorted(global_var_count.keys(), key=lambda x: global_var_count[x], reverse=True)[:K]
    global_var_count = {k: v for k, v in global_var_count.items() if k in chosen_global_vars}
    # stored_global_vars = stored_global_vars.intersection(chosen_global_vars)
    stored_global_vars = [var for var in chosen_global_vars if
                          var in stored_global_vars]  # keep the order to ensure reproducibility
    return chosen_global_vars, stored_global_vars, global_var_types


def get_global_variables(function):
    global_var_count: dict[str, int] = {}
    stored_global_vars = set()
    global_var_types: dict[str, str] = {}
    for block in function.blocks:
        for cmd in block.cmds:
            if isinstance(cmd, IRLoad):
                addr = cmd.src
                if addr[0] == '@':
                    global_var_types[addr] = cmd.typ
                    global_var_count[addr] = global_var_count.get(addr, 0) + 1
            elif isinstance(cmd, IRStore):
                addr = cmd.mem_dest
                if addr[0] == '@':
                    global_var_types[addr] = cmd.typ
                    global_var_count[addr] = global_var_count.get(addr, 0) + 1
                    stored_global_vars.add(addr)
    return global_var_count, stored_global_vars, global_var_types


def get_local_name(global_var: str):
    return renamer.get_name('%' + global_var[1:].removesuffix('.ptr')) + '.ptr'


def _inline_global_variables(function: IRFunction,
                             global_variables: list[str],
                             stored_global_vars: list[str],
                             global_var_types: dict[str, str]):
    if not global_variables:
        return
    local_names = {global_var: get_local_name(global_var) for global_var in global_variables}
    for block in function.blocks:
        for cmd in block.cmds:
            if isinstance(cmd, IRLoad) or isinstance(cmd, IRStore):
                addr = cmd.addr
                if addr in local_names:
                    cmd.addr = local_names[addr]
        if block.cmds and isinstance(block.cmds[-1], IRRet):
            store_cmds = []
            for global_var in stored_global_vars:
                local_ptr_name = local_names[global_var]
                local_val_name = renamer.get_name(local_ptr_name.removesuffix('.ptr') + '.val')
                typ = global_var_types[global_var]
                store_cmds.append(IRLoad(local_val_name, local_ptr_name, typ))
                store_cmds.append(IRStore(global_var, local_val_name, typ))
            block.cmds = block.cmds[:-1] + store_cmds + block.cmds[-1:]

    entry_block = function.blocks[0]
    allocas = [cmd for cmd in entry_block.cmds if isinstance(cmd, IRAlloca)]
    others = []

    for global_var in global_variables:
        local_ptr_name = local_names[global_var]
        local_val_name = renamer.get_name(local_ptr_name.removesuffix('.ptr') + '.val')
        typ = global_var_types[global_var]
        allocas.append(IRAlloca(local_ptr_name, typ))
        others.append(IRLoad(local_val_name, global_var, typ))
        others.append(IRStore(local_ptr_name, local_val_name, typ))

    others.extend([cmd for cmd in entry_block.cmds if not isinstance(cmd, IRAlloca)])
    entry_block.cmds = allocas + others


def inline_global_variables(function: IRFunction):
    """
    Convert frequently used global variables to local variables

    Load the global variable to a local variable at the beginning of the function, and store it back at the end.
    Currently, only leaf functions are considered
    """

    global_variables, stored_global_vars, global_var_types = get_variables_to_inline(function)
    _inline_global_variables(function, global_variables, stored_global_vars, global_var_types)
    return global_variables, stored_global_vars, global_var_types
