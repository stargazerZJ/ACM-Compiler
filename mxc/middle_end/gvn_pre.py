from copy import copy, deepcopy
from dataclasses import dataclass
from collections import defaultdict, deque
from typing import Optional, Dict, Set, List, Tuple

from mxc.common.dominator import DominatorTree
from mxc.common.ir_repr import IRBinOp, IRBlock, IRCmdBase, IRPhi, IRIcmp, IRGetElementPtr, IRFunction
from mxc.common.renamer import renamer
from mxc.middle_end.cfg_transform import copy_propagation
from mxc.middle_end.utils import mark_blocks, build_control_flow_graph, build_reverse_control_flow_graph


@dataclass(frozen=True)
class Expression:
    def depends_on(self) -> list[int]:
        return []

    def is_simple(self) -> bool:
        return isinstance(self, Temporary)


@dataclass(frozen=True)
class BinOpExpression(Expression):
    op: str  # Can be arithmetic op, icmp op, or 'gep'
    v1: int
    v2: int

    @classmethod
    def new(cls, op: str, v1: int, v2: int):
        if op in ['add', 'mul', 'and', 'or', 'xor']:
            return cls(op, min(v1, v2), max(v1, v2))
        return cls(op, v1, v2)

    def depends_on(self) -> list[int]:
        return [self.v1, self.v2]


@dataclass(frozen=True)
class Temporary(Expression):
    reg: str  # can be a register or a constant


class ValueTable:
    def __init__(self):
        self.expressions: Dict[Expression, int] = {}
        self.number = 0
        self.ir_expressions: list[IRCmdBase | None] = []

    def query_or_assign(self, expr: Expression, ir_exp: IRCmdBase | None) -> int:
        if expr in self.expressions:
            return self.expressions[expr]
        return self.assign(expr, None, ir_exp)

    def assign(self, exp: Expression, number: int | None = None, ir_exp: IRCmdBase | None = None):
        if number is None:
            number = self.number
            self.ir_expressions.append(ir_exp)
            self.number += 1
        self.expressions[exp] = number
        return number

    def query(self, expr: Expression) -> Optional[int]:
        return self.expressions.get(expr)

    def phi_translate(self, pred: IRBlock, succ: IRBlock,
                      value: int, expr: Expression, phi_gen: dict[int, list[tuple[int, Temporary]]]) -> tuple[int, Expression]:
        pred_index = succ.predecessors.index(pred)
        translate = lambda v: phi_gen[v][pred_index][0] if v in phi_gen else v
        if not isinstance(expr, BinOpExpression):
            return phi_gen[value][pred_index] if value in phi_gen else (value, expr)
        new_expr = BinOpExpression(
            expr.op,
            translate(expr.v1),
            translate(expr.v2)
        )
        if new_expr == expr:
            return value, expr
        return self.query_or_assign(new_expr, self.ir_expressions[value]), new_expr

    def reconstruct(self, avail_out: dict[int, Temporary], value: int, expr: BinOpExpression):
        new_ir_expr = deepcopy(self.ir_expressions[value])
        for i in range(2):
            if expr.depends_on()[i] in avail_out:
                new_ir_expr.var_use[i] = avail_out[expr.depends_on()[i]].reg
            else:
                original_name = new_ir_expr.var_use[i]
                assert not original_name.startswith('%') or original_name.endswith('.param'), \
                    f"Temporary {original_name} not found in avail_out"
        new_ir_expr.var_def[0] = renamer.get_name(new_ir_expr.var_def[0])
        return new_ir_expr

def clean(gen_set: dict[int, Expression], kill_set: dict[int, Temporary]):
    result = {}
    # Since Python 3.7, dict is ordered by insertion order
    # This feature is used to ensure that the gen_set is topologically sorted
    for value, expr in gen_set.items():
        if isinstance(expr, Temporary) and value in kill_set:
            continue
        if (isinstance(expr, BinOpExpression)
                and (expr.v1 not in result or expr.v2 not in result)):
            continue
        result[value] = expr
    return result

def build_sets(blocks: list[IRBlock],
               immediate_dominator: list[int],
               dominator_tree_order: list[int],
               post_dominator_tree_order: list[int],
               value_table: ValueTable) -> tuple[
    list[dict[int, Temporary]],
    list[dict[int, Expression]],
    list[dict[int, list[tuple[int, Temporary]]]]]:
    n = len(blocks)
    avail_out: list[dict[int, Temporary]] = [{} for _ in range(n)]
    antic_in: list[dict[int, Expression]] = [{} for _ in range(n)]
    phi_gen: list[dict[int, list[tuple[int, Temporary]]]] = [{} for _ in range(n)]
    tmp_gen: list[dict[int, Temporary]] = [{} for _ in range(n)]

    # Phase 1
    for i in dominator_tree_order:
        block = blocks[i]
        exp_gen: dict[int, Expression] = {}
        avail_out[i] = copy(avail_out[immediate_dominator[i]]) if i else {}
        for cmd in block.cmds:
            if not cmd.var_def:
                continue
            def_value = None
            tmp_def = Temporary(cmd.var_def[0])
            if isinstance(cmd, IRBinOp):
                tmp_use = [Temporary(var) for var in cmd.var_use]
                val_use = [value_table.query_or_assign(tmp, None) for tmp in tmp_use]
                for val, tmp in zip(val_use, tmp_use):
                    exp_gen.setdefault(val, tmp)
                op = cmd.op
                expr = BinOpExpression.new(op, *val_use)
                value = value_table.query_or_assign(expr, cmd)
                exp_gen.setdefault(value, expr)
                def_value = value
            elif isinstance(cmd, IRPhi):
                def_value = value_table.assign(tmp_def)
            if not isinstance(cmd, IRPhi):
                def_value = value_table.assign(tmp_def, def_value)
                tmp_gen[i].setdefault(def_value, tmp_def)
            avail_out[i].setdefault(def_value, tmp_def)
        antic_in[i] = clean(exp_gen, tmp_gen[i])

    # Phase 1.5
    for i, block in enumerate(blocks):
        for phi in block.cmds:
            if not isinstance(phi, IRPhi): break
            tmp_use = [Temporary(phi.lookup(pred)) for pred in block.predecessors]
            val_use = [value_table.query_or_assign(tmp, None) for tmp in tmp_use]
            def_value = value_table.query(Temporary(phi.dest))
            phi_gen[i][def_value] = list(zip(val_use, tmp_use))

    # Phase 2
    converged = False
    while not converged:
        converged = True
        for i in post_dominator_tree_order:
            block = blocks[i]
            antic_out = {}
            if len(block.successors) == 0:
                continue
            elif len(block.successors) > 1:
                a1, a2 = (antic_in[succ.index] for succ in block.successors)
                antic_out = {v: e for v, e in a1.items() if v in a2}
            else:
                succ = block.successors[0]
                succ_index = succ.index
                a = antic_in[succ_index]
                for v, e in a.items():
                    v_, e_ = value_table.phi_translate(block, succ, v, e, phi_gen[succ_index])
                    antic_out[v_] = e_
            new_antic_in = copy(antic_in[i])
            new_antic_in.update(antic_out)
            new_antic_in = clean(new_antic_in, tmp_gen[i])
            if new_antic_in != antic_in[i]:
                antic_in[i] = new_antic_in
                converged = False

    return avail_out, antic_in, phi_gen

def insert(blocks: list[IRBlock],
           dominator_tree_order: list[int],
           dominator_children: list[list[int]],
           avail_out: list[dict[int, Temporary]],
           antic_in: list[dict[int, Expression]],
           phi_gen: list[dict[int, list[tuple[int, Temporary]]]],
           value_table: ValueTable):
    converged = False
    while not converged:
        converged = True
        new_set: list[dict[int, Temporary]] = [{} for _ in range(len(blocks))]
        for i in dominator_tree_order:
            block = blocks[i]
            m = len(block.predecessors)
            if m > 1:
                for value, expr in antic_in[i].items():
                    if not isinstance(expr, BinOpExpression):
                        continue
                    translated = [value_table.phi_translate(pred, block, value, expr, phi_gen[i])
                                  for pred in block.predecessors]
                    leaders = [(avail_out[pred.index].get(value[0]))
                                  for value, pred in zip(translated, block.predecessors)]
                    if all(leaders) or not any(leaders):
                        continue
                    converged = False
                    for j, pred in enumerate(block.predecessors):
                        if leaders[j]:
                            continue
                        vt, et = translated[j]
                        new_cmd = value_table.reconstruct(avail_out[pred.index], vt, et)
                        typ = new_cmd.dest_typ
                        pred.cmds[-1:-1] = [new_cmd]
                        new_set[pred.index][vt] = tmp = Temporary(new_cmd.var_def[0])
                        avail_out[pred.index][vt] = tmp
                        leaders[j] = tmp
                        value_table.assign(tmp, vt)
                    # noinspection PyUnboundLocalVariable
                    phi_cmd = IRPhi(
                        renamer.get_name("%.gvn_pre"),
                        typ,
                        [(pred, leader.reg) for pred, leader in zip(block.predecessors, leaders)]
                    )
                    block.cmds[0:0] = [phi_cmd]
                    new_set[i][value] = tmp = Temporary(phi_cmd.dest)
                    avail_out[i][value] = tmp
                    value_table.assign(tmp, value)
                    phi_gen[i][value] = list(zip((vt for vt, _ in translated), leaders))
                avail_out[i].update(new_set[i])
            for c in dominator_children[i]:
                new_set[c].update(new_set[i])
                avail_out[c].update(new_set[i])


def eliminate(blocks: list[IRBlock],
              immediate_dominator: list[int],
              avail_out: list[dict[int, Temporary]],
              value_table: ValueTable):
    for i, block in enumerate(blocks):
        avail_in = copy(avail_out[immediate_dominator[i]]) if i else {}
        new_cmds = []
        for cmd in block.cmds:
            if not cmd.var_def:
                new_cmds.append(cmd)
                continue
            var_def = cmd.var_def[0]
            current_tmp = Temporary(var_def)
            current_value = value_table.query(current_tmp)
            leader = avail_in.get(current_value)
            if leader and leader.reg != var_def:
                move_cmd = IRBinOp(var_def, "add", leader.reg, "0", cmd.dest_typ)
                new_cmds.append(move_cmd)
            else:
                new_cmds.append(cmd)
            avail_in.setdefault(current_value, current_tmp)
        block.cmds = new_cmds

def gvn_pre(function: IRFunction):
    blocks = function.blocks
    mark_blocks(blocks)

    cfg = build_control_flow_graph(blocks)
    reverse_cfg, end_node = build_reverse_control_flow_graph(blocks)

    dom_tree = DominatorTree(cfg)
    dom_tree.compute()
    immediate_dominator = dom_tree.get_immediate_dominators()
    dominator_tree_order = dom_tree.get_dominator_tree_dfs_order()
    reverse_dom_tree = DominatorTree(reverse_cfg)
    reverse_dom_tree.compute(end_node)
    post_dominator_tree_order = reverse_dom_tree.get_dominator_tree_dfs_order()
    post_dominator_tree_order.pop(0) # Remove the end node

    dominator_children = [[] for _ in range(len(blocks))]
    for i, dom in enumerate(immediate_dominator[1:]):
        # immediate_dominator[0] is -1
        dominator_children[dom].append(i + 1)

    del dom_tree, reverse_dom_tree, cfg, reverse_cfg

    value_table = ValueTable()
    avail_out, antic_in, phi_gen = build_sets(
        blocks, immediate_dominator, dominator_tree_order, post_dominator_tree_order, value_table)
    insert(blocks, dominator_tree_order, dominator_children, avail_out, antic_in, phi_gen, value_table)
    eliminate(blocks, immediate_dominator, avail_out, value_table)

    # copy_propagation(function)
