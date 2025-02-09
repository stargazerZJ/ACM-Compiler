from antlr4 import ParserRuleContext
from .syntax_error import MxSyntaxError
from .type import TypeBase, FunctionType, ArrayType, ClassType, builtin_functions, builtin_types


class ScopeBase:
    def get_type(self, name: str, dimensions: int = 0, ctx: ParserRuleContext = None) -> TypeBase:
        raise MxSyntaxError(f"Type '{name}' not found", ctx)

    def get_variable(self, name: str, ctx: ParserRuleContext) -> tuple[TypeBase, str]:
        raise MxSyntaxError(f"Variable '{name}' not found", ctx)

    def add_variable(self, name: str, typ: TypeBase, ctx: ParserRuleContext, ir_name: str):
        raise MxSyntaxError(f"Variable '{name}' already defined", ctx)

    def push_scope(self, is_loop_scope: bool = False):
        pass

    def pop_scope(self):
        pass

    def can_break_or_continue(self) -> bool:
        return False

    def enter_class_scope(self, class_name: str):
        pass

    def exit_class_scope(self):
        pass

    def get_this_type(self) -> TypeBase:
        raise MxSyntaxError("Keyword 'this' not allowed here", None)

    def get_return_type(self) -> TypeBase:
        raise MxSyntaxError("Keyword 'return' not allowed here", None)

    def set_return_type(self, typ: TypeBase):
        raise MxSyntaxError("Keyword 'return' not allowed here", None)


class GlobalScope(ScopeBase):
    types: dict[str, TypeBase]
    global_functions: dict[str, FunctionType]

    def __init__(self):
        self.types = {}
        self.global_functions = {}
        for name, func in builtin_functions.items():
            self.global_functions[name] = func
        for name, typ in builtin_types.items():
            # The Lexer has made sure that no variable has the same name as a builtin type
            self.types[name] = typ

    def get_type(self, name: str, dimensions: int = 0, ctx: ParserRuleContext = None) -> TypeBase:
        if name in self.types:
            element_type = self.types[name]
        else:
            raise MxSyntaxError(f"Type '{name}' not found", ctx)
        return element_type if dimensions == 0 else ArrayType(element_type, dimensions)

    def register_class_name(self, name: str, ctx: ParserRuleContext):
        if name in self.types:
            raise MxSyntaxError(f"Class '{name}' already defined", ctx)
        self.types[name] = ClassType(name)

    def add_function(self, func: FunctionType, ctx: ParserRuleContext):
        if func.name in self.types or func.name in self.global_functions:
            raise MxSyntaxError(f"Function '{func.name}' already defined", ctx)
        self.global_functions[func.name] = func


class LocalScope:
    variables: dict[str, tuple[TypeBase, str]]
    is_loop_scope: bool
    is_class_scope: bool

    def __init__(self, is_loop_scope: bool, is_class_scope: bool = False):
        self.variables = {}
        self.is_loop_scope = is_loop_scope
        self.is_class_scope = is_class_scope


class Scope(ScopeBase):
    global_scope: GlobalScope
    scope_stack: list[LocalScope]
    this_type: TypeBase | None
    return_type: TypeBase

    def __init__(self, types: GlobalScope):
        self.global_scope = types
        self.scope_stack = [LocalScope(False)]
        self.this_type = None

    def get_type(self, name: str, dimensions=0, ctx: ParserRuleContext = None) -> TypeBase:
        return self.global_scope.get_type(name, dimensions, ctx)

    def get_variable(self, name: str, ctx: ParserRuleContext) -> tuple[TypeBase, str]:
        for scope in reversed(self.scope_stack):
            if name in scope.variables:
                return scope.variables[name]
        if name in self.global_scope.global_functions:
            func = self.global_scope.global_functions[name]
            return func, func.ir_name
        raise MxSyntaxError(f"Variable '{name}' not found", ctx)

    def add_variable(self, name: str, typ: TypeBase, ctx: ParserRuleContext, ir_name: str):
        if name in self.scope_stack[-1].variables:
            raise MxSyntaxError(f"Variable '{name}' already defined", ctx)
        if name in self.global_scope.global_functions:
            raise MxSyntaxError(f"Variable '{name}' already defined as a function", ctx)
        self.scope_stack[-1].variables[name] = typ, ir_name

    def push_scope(self, is_loop_scope: bool = False, is_class_scope: bool = False):
        self.scope_stack.append(LocalScope(is_loop_scope, is_class_scope))

    def pop_scope(self):
        self.scope_stack.pop()

    def can_break_or_continue(self) -> bool:
        for scope in reversed(self.scope_stack):
            if scope.is_loop_scope:
                return True
        return False

    def enter_class_scope(self, class_name: str):
        self.this_type = self.global_scope.get_type(class_name)
        self.scope_stack.append(LocalScope(False, True))
        for name, typ in self.this_type.members.items():
            self.scope_stack[-1].variables[name] = typ, "%.this." + name

    def exit_class_scope(self):
        self.this_type = None
        self.scope_stack.pop()

    def get_this_type(self) -> TypeBase:
        if self.this_type is None:
            raise MxSyntaxError("Keyword 'this' not allowed here", None)
        return self.this_type

    def get_return_type(self) -> TypeBase:
        return self.return_type

    def set_return_type(self, typ: TypeBase):
        self.return_type = typ

    def is_global(self):
        return len(self.scope_stack) == 1

    def is_in_class(self):
        if self.is_global():
            return False
        return self.scope_stack[1].is_class_scope
