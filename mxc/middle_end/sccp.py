from typing import cast

from mxc.common.ir_repr import IRFunction, IRBlock, IRPhi, IRCmdBase, IRLoad, IRCall, IRStore, IRJump, IRIcmp, IRBinOp, \
    IRBranch, IRGetElementPtr
from mxc.middle_end.mem2reg import IRUndefinedValue
from mxc.middle_end.mir import parse_imm, is_imm
from mxc.middle_end.utils import mark_blocks, collect_defs, collect_uses, collect_type_map


class Unknown:
    """
    Lattice cell values can be:
    - Unknown -> no information
    - int -> constant value
    - None -> identified as not a constant
    """
    pass


def meet(lhs: Unknown | int | None, rhs: Unknown | int | None) -> Unknown | int | None:
    if isinstance(lhs, Unknown):
        return rhs
    if isinstance(rhs, Unknown):
        return lhs
    if lhs == rhs:
        return lhs
    return None

def to_int32(value: int) -> int:
    return (value + 2**31) % 2**32 - 2**31

def to_imm(value: int, typ: str) -> str:
    if typ == "i32":
        return str(value)
    if typ == "i1":
        return "true" if value else "false"
    return "null"

class SparseConditionalConstantPropagation:
    def __init__(self, function: IRFunction):
        self.function = function
        self.blocks: list[IRBlock] = function.blocks
        self.defs = collect_defs(function)
        self.type_map = collect_type_map(function)
        self.use_sites = collect_uses(self.defs, self.blocks)

        self.lattice_cell: dict[str, Unknown | int | None] = {
            def_: Unknown() for def_ in self.defs
        }
        self.lattice_cell.update(
            {param + ".param": None for param in function.info.param_ir_names}
        )

        self.block_visited: set[int] = set()
        self.edge_visited: set[tuple[int, int]] = set()
        self.cfg_work_list: list[tuple[int, int]] = [(0, 0)]  # (from, to)
        self.ssa_work_list: list[tuple[IRBlock, int]] = []  # (block, command_id)

    def run(self):
        mark_blocks(self.blocks)
        while self.cfg_work_list or self.ssa_work_list:
            while self.cfg_work_list:
                from_, to = self.cfg_work_list.pop()
                if (from_, to) in self.edge_visited:
                    continue
                self.edge_visited.add((from_, to))
                self.visit_block(from_, to)
            while self.ssa_work_list:
                block, cmd_id = self.ssa_work_list.pop()
                if block.index not in self.block_visited:
                    continue
                self.visit_cmd(block, cmd_id)

        for block in self.blocks:
            if block.unreachable_mark or block.index not in self.block_visited:
                block.unreachable_mark = True
            for cmd in block.cmds:
                if self.update_value(cmd, block):
                    block.unreachable_mark = True

    def update_value(self, cmd: IRCmdBase, block: IRBlock) -> bool:
        for i, var_use in enumerate(cmd.var_use):
            if var_use in self.lattice_cell:
                literal = self.lattice_cell[var_use]
                if literal is None:
                    continue
                if isinstance(literal, Unknown):
                    if not isinstance(cmd, IRPhi):
                        return True # Unreachable
                    else:
                        self.function.edge_to_remove.add((cmd.sources[i], block))
                        continue
                cmd.var_use[i] = to_imm(literal, self.type_map[var_use])
            elif isinstance(var_use, IRUndefinedValue):
                if not isinstance(cmd, IRPhi):
                    return True  # Unreachable
                else:
                    self.function.edge_to_remove.add((cmd.sources[i], block))
                    continue
        if isinstance(cmd, IRBranch):
            if cmd.cond in ['true', 'false']:
                unreachable_dest = cmd.true_dest.get_dest() if cmd.cond == 'false' else cmd.false_dest.get_dest()
                self.function.edge_to_remove.add((block, unreachable_dest))

    def visit_block(self, from_: int, to: int):
        cmds = self.blocks[to].cmds
        for i, phi in enumerate(self.blocks[to].cmds):
            if not isinstance(phi, IRPhi):
                break
            self.visit_phi(to, i)
        if to in self.block_visited:
            return
        self.block_visited.add(to)
        # print(f"Visiting block {self.blocks[to].name}")

        for i, cmd in enumerate(cmds):
            if isinstance(cmd, IRPhi):
                continue
            self.visit_expr(to, i)

    def get_value(self, var: str | IRUndefinedValue) -> Unknown | int | None:
        if isinstance(var, IRUndefinedValue):
            return Unknown()
        if not var.startswith("%"):
            if var.startswith('@.str'):
                return None
            return parse_imm(var)
        return self.lattice_cell.get(var)

    def visit_phi(self, block_id: int, cmd_id: int):
        cmd = self.blocks[block_id].cmds[cmd_id]
        cmd = cast(IRPhi, cmd)
        new_value = Unknown()
        for var_use, source in zip(cmd.var_use, cmd.sources):
            if (source.index, block_id) not in self.edge_visited:
                continue
            new_value = meet(new_value, self.get_value(var_use))
        self.try_update(cmd.dest, new_value)

    def try_update(self, var: str, value: Unknown | int | None):
        if self.lattice_cell[var] != value:
            self.lattice_cell[var] = value
            self.ssa_work_list.extend(self.use_sites[var])

    def visit_cmd(self, block: IRBlock, cmd_id: int):
        cmd = block.cmds[cmd_id]
        block_id = block.index
        if isinstance(cmd, IRPhi):
            self.visit_phi(block_id, cmd_id)
        else:
            self.visit_expr(block_id, cmd_id)

    def visit_expr(self, block_id: int, cmd_id: int):
        block = self.blocks[block_id]
        cmd = block.cmds[cmd_id]
        # print(f"Visiting command {cmd}")

        if isinstance(cmd, IRLoad) or isinstance(cmd, IRCall) or isinstance(cmd, IRGetElementPtr):
            # The result of these commands is considered not a constant
            if cmd.dest:
                self.try_update(cmd.dest, None)
        elif isinstance(cmd, IRIcmp):
            lhs_value, rhs_value = self.get_value(cmd.lhs), self.get_value(cmd.rhs)
            if isinstance(lhs_value, Unknown) or isinstance(rhs_value, Unknown):
                return
            if cmd.lhs == cmd.rhs:
                if cmd.op in ['eq', 'sle', 'sge']:
                    return self.try_update(cmd.dest, 1)
                else:
                    return self.try_update(cmd.dest, 0)
            if lhs_value is None or rhs_value is None:
                return self.try_update(cmd.dest, None)
            if cmd.op == 'eq':
                return self.try_update(cmd.dest, int(lhs_value == rhs_value))
            elif cmd.op == 'ne':
                return self.try_update(cmd.dest, int(lhs_value != rhs_value))
            elif cmd.op == 'slt':
                return self.try_update(cmd.dest, int(lhs_value < rhs_value))
            elif cmd.op == 'sgt':
                return self.try_update(cmd.dest, int(lhs_value > rhs_value))
            elif cmd.op == 'sle':
                return self.try_update(cmd.dest, int(lhs_value <= rhs_value))
            elif cmd.op == 'sge':
                return self.try_update(cmd.dest, int(lhs_value >= rhs_value))
            else:
                assert False, "Unknown icmp operator"
        elif isinstance(cmd, IRBinOp):
            lhs_value, rhs_value = self.get_value(cmd.lhs), self.get_value(cmd.rhs)
            if isinstance(lhs_value, Unknown) or isinstance(rhs_value, Unknown):
                return
            if lhs_value is None or rhs_value is None:
                if cmd.lhs == cmd.rhs:
                    if cmd.op in ['sub', 'xor', 'ashr']:
                        return self.try_update(cmd.dest, 0)
                return self.try_update(cmd.dest, None)
            if cmd.op == 'add':
                return self.try_update(cmd.dest, to_int32(lhs_value + rhs_value))
            elif cmd.op == 'sub':
                return self.try_update(cmd.dest, to_int32(lhs_value - rhs_value))
            elif cmd.op == 'mul':
                return self.try_update(cmd.dest, to_int32(lhs_value * rhs_value))
            elif cmd.op == 'sdiv':
                if rhs_value == 0:
                    return  # remain `Unknown` for undefined behavior
                quotient = lhs_value // rhs_value
                if (lhs_value * rhs_value < 0) and (lhs_value % rhs_value != 0):
                    quotient += 1
                return self.try_update(cmd.dest, to_int32(quotient))
            elif cmd.op == 'srem':
                if rhs_value == 0:
                    return
                remainder = lhs_value % rhs_value
                if (lhs_value * rhs_value < 0) and remainder != 0:
                    remainder -= rhs_value
                return self.try_update(cmd.dest, to_int32(remainder))
            elif cmd.op == 'and':
                result = lhs_value & rhs_value
                return self.try_update(cmd.dest, to_int32(lhs_value & rhs_value))
            elif cmd.op == 'or':
                result = lhs_value | rhs_value
                return self.try_update(cmd.dest, to_int32(lhs_value | rhs_value))
            elif cmd.op == 'xor':
                result = lhs_value ^ rhs_value
                return self.try_update(cmd.dest, to_int32(lhs_value ^ rhs_value))
            elif cmd.op == 'shl':
                shift = rhs_value & 0x1F
                result = lhs_value << shift
                return self.try_update(cmd.dest, to_int32(result))
            elif cmd.op == 'ashr':
                shift = rhs_value & 0x1F
                result = lhs_value >> shift
                return self.try_update(cmd.dest, to_int32(result))
            else:
                assert False, "Unknown binop operator"
        elif isinstance(cmd, IRJump):
            self.cfg_work_list.append((block_id, cmd.dest.get_dest().index))
            return
        elif isinstance(cmd, IRBranch):
            cond_value = self.get_value(cmd.cond)
            # print(f"Branch condition: {cond_value}")

            if isinstance(cond_value, Unknown):
                return
            if cond_value is None:
                self.cfg_work_list.append((block_id, cmd.false_dest.get_dest().index))
                self.cfg_work_list.append((block_id, cmd.true_dest.get_dest().index))
                return
            if cond_value:
                self.cfg_work_list.append((block_id, cmd.true_dest.get_dest().index))
            else:
                self.cfg_work_list.append((block_id, cmd.false_dest.get_dest().index))


def sparse_conditional_constant_propagation(function: IRFunction):
    SparseConditionalConstantPropagation(function).run()