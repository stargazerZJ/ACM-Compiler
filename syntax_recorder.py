from typing import Any, Dict, Tuple, Type, TypeVar
from antlr4 import ParserRuleContext
from type import TypeBase, InternalPtrType, builtin_types, builtin_functions
from scope import GlobalScope


class VariableInfo:
    type: TypeBase
    ir_name: str

    def __init__(self, type_: TypeBase, ir_name: str):
        self.type = type_
        self.ir_name = ir_name

    def pointer_name(self):
        return f"{self.ir_name}.ptr"

    def value_name_hint(self):
        return self.ir_name.replace("@", "%") + ".val"


class FunctionInfo:
    name: str
    ir_name: str
    ret_type: TypeBase
    param_types: list[TypeBase]
    param_ir_names: list[str]
    local_vars: list[VariableInfo]
    is_member: bool

    def __init__(self, name: str = "", ir_name: str = "", ret_type: TypeBase = None, param_types: list[TypeBase] = None,
                 param_ir_names: list[str] = None,
                 is_member: bool = False):
        self.name = name
        self.ir_name = ir_name
        self.ret_type = ret_type
        self.param_types = param_types
        self.param_ir_names = param_ir_names
        self.local_vars = []
        self.is_member = is_member


builtin_function_infos: Dict[str, FunctionInfo] = {
    func.ir_name: FunctionInfo(name, func.ir_name, func.ret_type.internal_type(),
                       [typ.internal_type() for typ in func.param_types], [""] * len(func.param_types))
    for name, func in builtin_functions.items()
}


class ClassInfo:
    ir_name: str
    members: Dict[str, VariableInfo | FunctionInfo]
    member_idx: Dict[str, int]
    size: int  # size of the class in bytes
    ctor: FunctionInfo | None

    def __init__(self, ir_name: str):
        self.ir_name = ir_name
        self.members = {}
        self.member_idx = {}
        self.size = 0
        self.ctor = None

    def get_member(self, name: str) -> VariableInfo | FunctionInfo:
        return self.members[name]

    def get_member_idx(self, name: str) -> int:
        return self.member_idx[name]

    def add_member(self, name: str, info: VariableInfo | FunctionInfo):
        self.members[name] = info
        if isinstance(info, VariableInfo):
            self.member_idx[name] = len(self.members) - 1
            self.size += 4

    def get_size(self) -> int:
        return self.size


internal_array_info: ClassInfo = ClassInfo("%.arr")  # only used in multidimensional arrays
internal_array_info.members = {"data": VariableInfo(InternalPtrType(builtin_types["null"]), "%.arr.data"),
                               "size": VariableInfo(builtin_types["int"], "%.arr.size")}
internal_array_info.member_idx = {"data": 0, "size": 1}
internal_array_info.size = 8

T = TypeVar('T')


class SyntaxRecorder:
    """Record syntax information"""
    info: Dict[Tuple[int, int], Any]  # (line, col) -> info
    global_scope: GlobalScope
    function_info: Dict[str, FunctionInfo]
    current_function: FunctionInfo | None
    class_info: Dict[str, ClassInfo]

    def __init__(self, global_scope: GlobalScope):
        self.info = {}
        self.global_scope = global_scope
        self.function_info = builtin_function_infos.copy()
        self.current_function = None
        self.class_info = {"%.arr": internal_array_info}

    def record(self, ctx: ParserRuleContext, info: Any):
        assert (ctx.start.line, ctx.start.column) not in self.info
        self.info[(ctx.start.line, ctx.start.column)] = info

    def get_info(self, ctx: ParserRuleContext) -> Any:
        return self.info.get((ctx.start.line, ctx.start.column), None)

    def get_typed_info(self, ctx: ParserRuleContext, expected_type: Type[T]) -> T:
        info = self.get_info(ctx)
        if not isinstance(info, expected_type):
            raise TypeError(f"Expected type {expected_type}, but got {type(info)}.")
        return info

    def enter_function(self, function_info: FunctionInfo, ctx: ParserRuleContext):
        self.current_function = function_info
        self.function_info[function_info.ir_name] = function_info
        self.record(ctx, function_info)

    def exit_function(self):
        self.current_function = None

    def get_function_info(self, ir_name: str) -> FunctionInfo:
        return self.function_info[ir_name]

    def get_class_info(self, ir_name: str) -> ClassInfo:
        return self.class_info[ir_name]
