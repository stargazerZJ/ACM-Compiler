from ir_utils import renamer
from typing import Any, Dict, Tuple, Type, TypeVar
from antlr4 import ParserRuleContext
from type import TypeBase
from scope import GlobalScope


class VariableInfo:
    type: TypeBase
    ir_name: str

    def __init__(self, type_: TypeBase, ir_name: str):
        self.type = type_
        self.ir_name = ir_name


T = TypeVar('T')


class SyntaxRecorder:
    """Record syntax information"""
    info: Dict[Tuple[int, int], Any]  # (line, col) -> info
    global_scope: GlobalScope

    def __init__(self, global_scope: GlobalScope):
        self.info = {}
        self.global_scope = global_scope

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
