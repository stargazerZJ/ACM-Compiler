from antlr4 import ParserRuleContext
from syntax_error import MxSyntaxError
from types import TypeBase, FunctionType, ArrayType, builtin_functions, builtin_types





class ScopeBase:
    def get_type(self, name: str, ctx: ParserRuleContext = None) -> TypeBase:
        raise MxSyntaxError(f"Type '{name}' not found", ctx)

    def get_variable(self, name: str, ctx: ParserRuleContext = None) -> TypeBase:
        raise MxSyntaxError(f"Variable '{name}' not found", ctx)

    def add_variable(self, name: str, typ: TypeBase, ctx: ParserRuleContext = None):
        raise MxSyntaxError(f"Variable '{name}' already defined", ctx)

    def can_break_or_continue(self) -> bool:
        return False

class GlobalTypeScope:
    types: dict[str, TypeBase]

    def __init__(self):
        self.types = {}
        self.variables = {}
        for typ in builtin_functions:
            self.types[typ.name] = typ
            self.variables[typ.name] = typ
        for typ in builtin_types:
            self.types[typ.name] = typ
            # self.variables[typ.name] = typ    # The Lexer has made sure that no variable has the same name as a builtin type

    def get_type(self, name: str, ctx: ParserRuleContext = None) -> TypeBase:
        if name in self.types:
            return self.types[name]
        raise MxSyntaxError(f"Type '{name}' not found", ctx)

class LocalScope:
    variables: dict[str, TypeBase]
    is_loop_scope: bool

    def __init__(self, is_loop_scope: bool):
        self.variables = {}
        self.is_loop_scope = is_loop_scope

class Scope(ScopeBase):
    types: GlobalTypeScope
    scope_stack: list[LocalScope]

    def __init__(self, types: GlobalTypeScope):
        self.types = types
        self.scope_stack = [LocalScope(False)]

    def get_type(self, name: str, ctx: ParserRuleContext = None) -> TypeBase:
        return self.types.get_type(name, ctx)

    def get_variable(self, name: str, ctx: ParserRuleContext = None) -> TypeBase:
        for scope in reversed(self.scope_stack):
            if name in scope.variables:
                return scope.variables[name]
        raise MxSyntaxError(f"Variable '{name}' not found", ctx)

    def add_variable(self, name: str, typ: TypeBase, ctx: ParserRuleContext = None):
        if name in self.scope_stack[-1].variables:
            raise MxSyntaxError(f"Variable '{name}' already defined", ctx)
        self.scope_stack[-1].variables[name] = typ

    def push_scope(self, is_loop_scope: bool):
        self.scope_stack.append(LocalScope(is_loop_scope))

    def pop_scope(self):
        self.scope_stack.pop()

    def can_break_or_continue(self) -> bool:
        for scope in reversed(self.scope_stack):
            if scope.is_loop_scope:
                return True
        return False
