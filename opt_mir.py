from ir_renamer import renamer
from ir_repr import IRBlock, IRBinOp, IRIcmp, IRGetElementPtr, IRCmdBase, IRStore, IRRet, IRBranch


def is_imm(s: str):
    return not s.startswith("%") and not s.startswith("@")


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


def mir_builder(block: IRBlock):
    new_list: list[IRCmdBase] = []
    # opt: merge icmp and branch (future)
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
                if is_imm(cmd.lhs):
                    li_lhs(cmd, new_list)
                if is_imm(cmd.rhs):
                    # opt: x / const optimization (future)
                    li_rhs(cmd, new_list)
            new_list.append(cmd)
        elif isinstance(cmd, IRIcmp):
            if cmd.op in ["eq", "neq"]:
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
                xor_cmd = IRBinOp(cmd.dest, "xor", cmd.var_use[0], "true", "i1")
                cmd.var_def[0] = name
                new_list.append(cmd)
                new_list.append(xor_cmd)
            else:
                new_list.append(cmd)
        elif isinstance(cmd, IRGetElementPtr):
            # Not compatible with LLVM IR, as IR disallows pointer arithmetic
            operand = cmd.ptr
            if cmd.arr_index != "0":
                shl_offset = {"%.arr": "3", "i32" : "2", "ptr" : "2", "i1" :"0"}[cmd.typ.ir_name]
                if shl_offset != "0":
                    name = renamer.get_name("%.shl")
                    shl_cmd = IRBinOp(name, "shl", cmd.arr_index, "2", "i32")
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
            if cmd.member_offset != 0:
                member_cmd = IRBinOp(cmd.dest, "add", operand, cmd.member_offset, "ptr")
                commutative_law(member_cmd, new_list)
            else:
                new_list[-1].var_def[0] = cmd.dest
        elif isinstance(cmd, IRStore):
            if is_imm(cmd.src):
                li_name = add_li(new_list, cmd.src, cmd.typ)
                cmd.var_use[1] = li_name
            new_list.append(cmd)
        elif isinstance(cmd, IRBranch):
            if is_imm(cmd.cond):
                li_name = add_li(new_list, cmd.cond, "i1")
                cmd.var_use[0] = li_name
            new_list.append(cmd)
        # elif isinstance(cmd, IRRet):
        #     if cmd.value and is_imm(cmd.value):
        #         li_name = add_li(new_list, cmd.value, cmd.typ)
        #         cmd.var_use[1] = li_name
        #     new_list.append(cmd)
        else:
            new_list.append(cmd)
        # opt: merge addi and load/store (future)
        block.cmds = new_list

