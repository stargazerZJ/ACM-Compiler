from mxc.common.renamer import renamer
from mxc.common.ir_repr import IRBlock, IRBinOp, IRIcmp, IRGetElementPtr, IRCmdBase, IRStore, IRRet, IRBranch, IRFunction, IRCall, \
    BBExit, unreachable_block
from mxc.frontend.ir_generation.block_chain import BlockChain
from .mem2reg import IRUndefinedValue


def is_imm(s: str):
    return isinstance(s, IRUndefinedValue) or not s.startswith("%") and not s.startswith("@")


def is_zero(s: str):
    return s == "0" or s == "false" or s == "null"


def add_li(new_list: list, value: str, typ: str = "i32") -> str:
    name = renamer.get_name("%.li")
    new_list.append(IRBinOp(name, "add", "0", value, typ))
    return name


def li_lhs(cmd, new_list):
    li_name = add_li(new_list, cmd.lhs, cmd.typ)
    cmd.var_use[0] = li_name


def li_rhs(cmd, new_list):
    li_name = add_li(new_list, cmd.rhs, cmd.typ)
    cmd.var_use[1] = li_name


def swap_operands(cmd):
    cmd.var_use = [cmd.var_use[1], cmd.var_use[0]]


def commutative_law(cmd, new_list):
    if is_imm(cmd.lhs):
        # swap lhs and rhs
        swap_operands(cmd)
    if is_imm(cmd.lhs):
        # if both operands are imm, add a li (temporary)
        li_lhs(cmd, new_list)
    if is_imm(cmd.rhs) and imm_overflow(cmd.rhs):
        # cannot be represented as 12-bit imm
        li_rhs(cmd, new_list)


def parse_imm(value: str):
    if value in ["true", "false", "null"]:
        value = 0 if value != "true" else 1
    return int(value)


def imm_overflow(value: str) -> bool:
    return parse_imm(value) > 2047 or parse_imm(value) < -2048


def is_power_of_two(value: int) -> bool:
    return value != 0 and (value & (value - 1)) == 0


def division_by_invariant_integer(n: str, d: int) -> list[IRBinOp]:
    """Generate LLVM IR code for division by a constant"""
    # param n is the name of the dividend, a signed 32-bit integer
    # param d is the divisor, a signed 32-bit integer
    # return a list of IRBinOp commands
    # note that this is a compiler intended for RV32IMA.
    cmds = []
    if is_power_of_two(d):
        srai_var = renamer.get_name("%.srai")
        cmds.append(IRBinOp(srai_var, "ashr", n, "31", "i32"))
        and_var = renamer.get_name("%.and")
        and_cmd = IRBinOp(and_var, "and", srai_var, str(d - 1), "i32")
        if d > 2048:
            li_rhs(and_cmd, cmds)
        cmds.append(and_cmd)
        add_var = renamer.get_name("%.add")
        cmds.append(IRBinOp(add_var, "add", n, and_var, "i32"))
        output_var = renamer.get_name("%.magic")
        cmds.append(IRBinOp(output_var, "ashr", add_var, str(d.bit_length() - 1), "i32"))
        return cmds

    # Handle special cases
    if d == 0:
        # raise ValueError("Division by zero")
        return [IRBinOp(n, "add", n, "0", "i32")]  # nop
    if d == 1:
        return [IRBinOp(n, "add", n, "0", "i32")]  # nop
    if d == -1:
        neg_var = renamer.get_name("%.neg")
        return [IRBinOp(neg_var, "sub", "0", n, "i32")]

    # Convert negative divisors to positive
    abs_d = abs(d)

    # Calculate magic numbers
    l = (abs_d - 1).bit_length()
    M = 1 + ((1 << (31 + l)) // abs_d) - (1 << 32)
    s = l - 1

    # Generate the IR operations
    ops = []

    # Step 1: Multiply by magic number
    mulh_var = renamer.get_name("%.mulh")
    cmd = IRBinOp(mulh_var, "smulh", n, str(M), "i32")
    li_rhs(cmd, ops)
    ops.append(cmd)

    if M < 0:
        add_var = renamer.get_name("%.add")
        ops.append(IRBinOp(add_var, "add", mulh_var, n, "i32"))
        mulh_var = add_var

    # Step 3: Arithmetic right shift
    if s > 0:
        shift_var = renamer.get_name("%.shift")
        ops.append(IRBinOp(shift_var, "ashr", mulh_var, str(s), "i32"))
        mulh_var = shift_var

    # Step 4: Add 1 for negative numbers (floor division)
    sign_var = renamer.get_name("%.sign")
    ops.append(IRBinOp(sign_var, "ashr", n, "31", "i32"))

    result_var = renamer.get_name("%.div")
    ops.append(IRBinOp(result_var, "sub", mulh_var, sign_var, "i32"))

    # Handle negative divisor by negating result
    if d < 0:
        neg_var = renamer.get_name("%.neg")
        ops.append(IRBinOp(neg_var, "sub", "0", result_var, "i32"))

    return ops


def build_mir_block(block: IRBlock, icmp_map: dict[str, IRIcmp], function: IRFunction):
    new_list: list[IRCmdBase] = []
    for cmd in block.cmds:
        if isinstance(cmd, IRBinOp):
            if cmd.op in ["add", "and", "or", "xor"]:
                commutative_law(cmd, new_list)
            elif cmd.op == "sub" and cmd.lhs == "0":
                # will be translated to "neg"
                pass
            elif cmd.op in ["sub", "shl", "ashr"]:
                # there is no shr in input IR
                if is_imm(cmd.lhs):
                    li_lhs(cmd, new_list)
                if is_imm(cmd.rhs) and imm_overflow(cmd.rhs):
                    li_rhs(cmd, new_list)
            elif cmd.op in ["mul", "sdiv", "srem"]:
                if cmd.op == "mul" and is_imm(cmd.lhs):
                    swap_operands(cmd)
                if is_imm(cmd.lhs):
                    li_lhs(cmd, new_list)
                if is_imm(cmd.rhs):
                    imm = parse_imm(cmd.rhs)
                    if cmd.op == "mul" and is_power_of_two(imm):
                        new_list.append(IRBinOp(cmd.dest, "shl", cmd.lhs, str(imm.bit_length() - 1), cmd.typ))
                        continue
                    elif cmd.op == "sdiv":
                        cmds = division_by_invariant_integer(cmd.lhs, imm)
                        cmds[-1].var_def[0] = cmd.dest
                        new_list.extend(cmds)
                        continue
                    else:
                        li_rhs(cmd, new_list)
            new_list.append(cmd)
        elif isinstance(cmd, IRIcmp):
            icmp_map[cmd.dest] = IRIcmp(cmd.dest, cmd.op, cmd.typ, cmd.lhs, cmd.rhs)
            if cmd.op in ["eq", "ne"]:
                if is_zero(cmd.lhs):
                    swap_operands(cmd)
                if is_zero(cmd.rhs):
                    # will be translated to "seqz" or "snez"
                    if is_imm(cmd.lhs):
                        # special case: imm == 0 (temporary)
                        li_lhs(cmd, new_list)
                else:
                    name = renamer.get_name("%.xor")
                    xor_cmd = IRBinOp(name, "xor", cmd.lhs, cmd.rhs, cmd.typ)
                    commutative_law(xor_cmd, new_list)
                    new_list.append(xor_cmd)
                    cmd.var_use[0] = name
                    cmd.var_use[1] = "0"
                new_list.append(cmd)
                continue
            inv = False
            if cmd.op in ["sle", "sge"]:
                inv = True
                cmd.op = "sgt" if cmd.op == "sle" else "slt"
            if cmd.op == "sgt":
                swap_operands(cmd)
                cmd.op = "slt"
            if is_imm(cmd.lhs) and -2048 <= int(cmd.lhs) + 1 <= 2047:
                # 2 < a -> !(a < 3)
                operand = int(cmd.lhs) + 1
                swap_operands(cmd)
                cmd.var_use[1] = str(operand)
                inv = not inv
            if is_imm(cmd.lhs):
                li_lhs(cmd, new_list)
            if is_imm(cmd.rhs) and imm_overflow(str(-int(cmd.rhs))):
                li_rhs(cmd, new_list)
            if inv:
                name = renamer.get_name("%.inv")
                xor_cmd = IRBinOp(cmd.dest, "xor", name, "true", "i1")
                cmd.var_def[0] = name
                new_list.append(cmd)
                new_list.append(xor_cmd)
            else:
                new_list.append(cmd)
        elif isinstance(cmd, IRGetElementPtr):
            # Not compatible with LLVM IR, as IR disallows pointer arithmetic
            operand = cmd.ptr
            flag = False  # command added
            if cmd.arr_index != "0":
                shl_offset = {"%.arr": "3", "i32": "2", "ptr": "2", "i1": "0"}[cmd.typ.ir_name]
                if shl_offset != "0":
                    name = renamer.get_name("%.shl")
                    shl_cmd = IRBinOp(name, "shl", cmd.arr_index, shl_offset, "i32")
                    if is_imm(cmd.arr_index):
                        li_lhs(shl_cmd, new_list)
                    new_list.append(shl_cmd)
                    add_name = renamer.get_name("%.add")
                    add_cmd = IRBinOp(add_name, "add", name, cmd.ptr, "ptr")
                    new_list.append(add_cmd)
                    operand = cmd.ptr
                else:
                    add_name = renamer.get_name("%.add")
                    add_cmd = IRBinOp(add_name, "add", cmd.arr_index, cmd.ptr, "ptr")
                    commutative_law(add_cmd, new_list)
                    new_list.append(add_cmd)
                    operand = cmd.ptr
                flag = True
            if cmd.member_offset != 0:
                member_cmd = IRBinOp(cmd.dest, "add", operand, str(cmd.member_offset), "ptr")
                commutative_law(member_cmd, new_list)
                new_list.append(member_cmd)
                flag = True
            if flag:
                new_list[-1].var_def[0] = cmd.dest
            else:
                new_list.append(IRBinOp(cmd.dest, "add", cmd.ptr, "0", "ptr"))
        elif isinstance(cmd, IRStore):
            if is_imm(cmd.src) and not is_zero(cmd.src):
                li_name = add_li(new_list, cmd.src, cmd.typ)
                cmd.var_use[1] = li_name
            new_list.append(cmd)
        elif isinstance(cmd, IRBranch):
            if is_imm(cmd.cond):
                li_name = add_li(new_list, cmd.cond, "i1")
                cmd.var_use[0] = li_name
            elif cmd.cond in icmp_map:
                icmp_cmd = icmp_map[cmd.cond]
                icmp_name = renamer.get_name("%.br")
                icmp_cmd = IRIcmp(icmp_name, icmp_cmd.op, icmp_cmd.typ, icmp_cmd.lhs, icmp_cmd.rhs)
                if is_zero(icmp_cmd.lhs):
                    swap_operands(icmp_cmd)
                    icmp_cmd.op = {"eq": "eq", "ne": "ne", "slt": "sgt", "sgt": "slt", "sle": "sge", "sge": "sle"}[
                        icmp_cmd.op]
                if is_imm(icmp_cmd.lhs):
                    li_lhs(icmp_cmd, new_list)
                if is_imm(icmp_cmd.rhs) and not is_zero(icmp_cmd.rhs):
                    li_rhs(icmp_cmd, new_list)
                cmd.set_icmp(icmp_cmd)
            new_list.append(cmd)
        elif isinstance(cmd, IRRet):
            # if cmd.value and is_imm(cmd.value):
            #     # This is done in asm_builder
            #     li_name = add_li(new_list, cmd.value, cmd.typ)
            #     cmd.var_use[1] = li_name
            last_cmd = new_list[-1] if new_list else None
            if isinstance(last_cmd, IRCall) and last_cmd.var_def == cmd.var_use[1:]:
                if last_cmd.func.ir_name == function.info.ir_name:
                    # convert self-recursive tail call into loop
                    last_cmd.set_tail_call()
                    last_cmd.self_tail_call = True
                    block.successors = [unreachable_block]
                    BlockChain.link_exits_to_block([BBExit(block, 0)], function.blocks[0])
                # elif len(last_cmd.func.param_types) <= 8:
                #     last_cmd.set_tail_call()
                else:
                    last_cmd.set_tail_call()
                    # new_list.append(cmd)
            else:
                new_list.append(cmd)
        else:
            new_list.append(cmd)
        # opt: merge addi and load/store (future)
    block.cmds = new_list


def mir_builder(function: IRFunction):
    icmp_map = {}
    for block in function.blocks:
        build_mir_block(block, icmp_map, function)
