import sys
from pathlib import Path

from main import OPTIMIZATION_PRESETS, OptimizationPass
from mxc.common.ir_repr import IRBlock, IRFunction, IRCall, IRJump, BBExit, IRPhi, IRBinOp, IRBranch, IRRet, IRModule
from mxc.common.renamer import renamer
from mxc.frontend.semantic.syntax_recorder import FunctionInfo
from mxc.frontend.semantic.type import builtin_types, builtin_functions
from mxc.middle_end.cfg_transform import copy_propagation
from mxc.middle_end.dce import naive_dce
from mxc.middle_end.gvn_pre import gvn_pre


def build_ir_module():
    # Create the function declarations
    func_foo = FunctionInfo(ir_name="@foo", param_types=[], param_ir_names = [], ret_type=builtin_types["int"])
    func_getcond = FunctionInfo(ir_name="@getcond", param_types=[], param_ir_names = [], ret_type=builtin_types["bool"])

    # Create the blocks
    block0 = IRBlock("entry")
    block1 = IRBlock("block1")
    block2 = IRBlock("block2")
    block3 = IRBlock("block3")
    block4 = IRBlock("block4")
    block5 = IRBlock("block5")
    block6 = IRBlock("block6")
    block_exit = IRBlock("block_exit")

    # Creating the function
    main_function_info = FunctionInfo(ir_name="@main", param_types=[], param_ir_names = [], ret_type=builtin_types["int"])
    main_function = IRFunction(info=main_function_info)

    # Add blocks to the function
    main_function.blocks = [block0, block1, block2, block3, block4, block5, block6, block_exit]

    # Block 0
    block0.add_cmd(IRJump(dest=BBExit(block0, 0)))
    block0.successors = [block1]

    # Block 1
    block1.predecessors = [block0]
    t1_call = IRCall(dest="%t1", func=func_foo, args=[])
    block1.add_cmd(t1_call)
    block1.add_cmd(IRJump(dest=BBExit(block1, 0)))
    block1.successors = [block2]

    # Block 2
    block2.predecessors = [block1, block6]
    t2_phi = IRPhi(dest="%t2", typ="i32", values=[(block1, "%t1"), (block6, "%t3")])
    block2.add_cmd(t2_phi)
    t3_binop = IRBinOp(dest="%t3", op="add", lhs="%t2", rhs="1", typ="i32")
    block2.add_cmd(t3_binop)
    cond_call = IRCall(dest="%cond", func=func_getcond, args=[])
    block2.add_cmd(cond_call)
    block2.add_cmd(IRBranch(cond="%cond", true_dest=BBExit(block2, 0), false_dest=BBExit(block2, 1)))
    block2.successors = [block3, block_exit]

    # Block 3
    block3.predecessors = [block2]
    cond2_call = IRCall(dest="%cond2", func=func_getcond, args=[])
    block3.add_cmd(cond2_call)
    block3.add_cmd(IRBranch(cond="%cond2", true_dest=BBExit(block3, 0), false_dest=BBExit(block3, 1)))
    block3.successors = [block4, block5]

    # Block 4
    block4.predecessors = [block3]
    t4_binop = IRBinOp(dest="%t4", op="add", lhs="%t2", rhs="%t3", typ="i32")
    block4.add_cmd(t4_binop)
    t6_binop = IRBinOp(dest="%t6", op="add", lhs="%t1", rhs="%t4", typ="i32")
    block4.add_cmd(t6_binop)
    block4.add_cmd(IRJump(dest=BBExit(block4, 0)))
    block4.successors = [block6]

    # Block 5
    block5.predecessors = [block3]
    t7_binop = IRBinOp(dest="%t7", op="add", lhs="%t3", rhs="1", typ="i32")
    block5.add_cmd(t7_binop)
    block5.add_cmd(IRJump(dest=BBExit(block5, 0)))
    block5.successors = [block6]

    # Block 6
    block6.predecessors = [block4, block5]
    t8_phi = IRPhi(dest="%t8", typ="i32", values=[(block4, "%t1"), (block5, "%t7")])
    block6.add_cmd(t8_phi)
    t9_binop = IRBinOp(dest="%t9", op="add", lhs="%t2", rhs="%t3", typ="i32")
    block6.add_cmd(t9_binop)
    t10_binop = IRBinOp(dest="%t10", op="add", lhs="%t9", rhs="%t8", typ="i32")
    block6.add_cmd(t10_binop)
    t11_call = IRCall(dest="%t11", func=func_foo, args=[])
    block6.add_cmd(t11_call)
    t12_binop = IRBinOp(dest="%t12", op="add", lhs="%t9", rhs="%t11", typ="i32")
    block6.add_cmd(t12_binop)
    t13_binop = IRBinOp(dest="%t13", op="add", lhs="%t12", rhs="%t3", typ="i32")
    block6.add_cmd(t13_binop)
    block6.add_cmd(IRJump(dest=BBExit(block6, 0)))
    block6.successors = [block2]

    # Block Exit
    block_exit.predecessors = [block2]
    ret = IRRet(typ="i32", value="0")
    block_exit.add_cmd(ret)

    # Register the names in the renamer
    renamer.reset()
    for block in main_function.blocks:
        renamer.register_name(block.name)
        for cmd in block.cmds:
            for var in cmd.var_def:
                renamer.register_name(var)

    # Now the IRFunction's internal representation is built
    ir_module = IRModule()
    ir_module.functions = [main_function, IRFunction(info=func_foo), IRFunction(info=func_getcond)]
    return ir_module

OPTIMIZATION_PRESETS["gvn_pre_test"] = [
    OptimizationPass(gvn_pre, "Global Value Numbering - Partial Redundancy Elimination"),
    OptimizationPass(copy_propagation, "Copy Propagation"),
    # OptimizationPass(naive_dce, "Dead Code Elimination (post GVN)"),
]

if __name__ == "__main__":
    ir = build_ir_module()

    Path("dumps").mkdir(exist_ok=True)
    counter = 0
    with open(f"dumps/ir-{counter}-initial.ll", "w") as f:
        print(ir.llvm(), file=f)

    optimization_level = "gvn_pre_test"

    try:
        for opt_pass in OPTIMIZATION_PRESETS[optimization_level]:
            print(f"Running {opt_pass.name}...", file=sys.stderr)
            opt_pass.apply(ir)

            # Dump intermediate results if requested
            counter += 1
            with open(f"dumps/ir-{counter}-after-{opt_pass.name}.ll", "w") as f:
                print(ir.llvm(), file=f)
        print(ir.llvm())
    except Exception as e:
        print(f"Optimization failed: {e}", file=sys.stderr)
        sys.exit(1)
