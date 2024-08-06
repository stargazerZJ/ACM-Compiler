from antlr4 import ParserRuleContext
from syntax_error import MxSyntaxError


class TypeBase:
    name: str
    members: dict[str, "TypeBase"]

    def __init__(self, name: str):
        self.name = name
        self.members = {}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TypeBase):
            return self.name == other.name
        return False

    def add_member(self, name: str, typ: "TypeBase"):
        self.members[name] = typ

    def get_member(self, name: str, ctx: ParserRuleContext = None) -> "TypeBase":
        if name in self.members:
            return self.members[name]
        raise MxSyntaxError(f"Type '{self.name}' has no member named '{name}'", ctx)

    def call(self, param_types: list["TypeBase"], ctx: ParserRuleContext = None) -> "TypeBase":
        raise MxSyntaxError(f"Type '{self.name}' cannot be called as a function", ctx)

    def subscript(self, ctx: ParserRuleContext = None) -> "TypeBase":
        raise MxSyntaxError(f"Type '{self.name}' cannot be subscripted", ctx)


class FunctionType(TypeBase):
    ret_type: TypeBase
    param_types: list[TypeBase]

    def __init__(self, name: str, ret_type: TypeBase, param_types: list[TypeBase]):
        super().__init__(name)
        self.ret_type = ret_type
        self.param_types = param_types

    def call(self, param_types: list[TypeBase], ctx: ParserRuleContext = None) -> TypeBase:
        if len(param_types) != len(self.param_types):
            raise MxSyntaxError(
                f"Function call error: expected {len(self.param_types)} parameters, got {len(param_types)}", ctx)
        for expected, actual in zip(self.param_types, param_types):
            if expected != actual:
                raise MxSyntaxError(
                    f"Function call error: expected parameter of type {expected.name}, got {actual.name}", ctx)
        return self.ret_type


class ArrayType(TypeBase):
    element_type: TypeBase
    dimension: int

    def __init__(self, element_type: TypeBase, dimension: int):
        super().__init__(f"{element_type.name}" + "[]" * dimension)
        self.element_type = element_type
        self.dimension = dimension
        self.add_member("size", FunctionType("size", BuiltinIntType(), []))

    def subscript(self, ctx: ParserRuleContext = None) -> TypeBase:
        if self.dimension == 1:
            return self.element_type
        return ArrayType(self.element_type, self.dimension - 1)


class BuiltinIntType(TypeBase):
    def __init__(self):
        super().__init__("int")


class BuiltinBoolType(TypeBase):
    def __init__(self):
        super().__init__("bool")


class BuiltinVoidType(TypeBase):
    def __init__(self):
        super().__init__("void")


class BuiltinStringType(TypeBase):
    def __init__(self):
        super().__init__("string")
        self.add_member("length", FunctionType("length", BuiltinIntType(), []))
        self.add_member("substring", FunctionType("substring", self, [BuiltinIntType(), BuiltinIntType()]))
        self.add_member("parseInt", FunctionType("parseInt", BuiltinIntType(), []))
        self.add_member("ord", FunctionType("ord", BuiltinIntType(), []))


class BuiltinNullType(TypeBase):
    def __init__(self):
        super().__init__("null")


class ClassType(TypeBase):
    def __init__(self, name: str):
        super().__init__(name)


builtin_types = [
    BuiltinIntType(),
    BuiltinBoolType(),
    BuiltinVoidType(),
    BuiltinStringType(),
    BuiltinNullType(),  # a special type for null literal
]

builtin_functions = [
    FunctionType("print", BuiltinVoidType(), [BuiltinStringType()]),
    FunctionType("println", BuiltinVoidType(), [BuiltinStringType()]),
    FunctionType("printInt", BuiltinVoidType(), [BuiltinIntType()]),
    FunctionType("printlnInt", BuiltinVoidType(), [BuiltinIntType()]),
    FunctionType("getString", BuiltinStringType(), []),
    FunctionType("getInt", BuiltinIntType(), []),
    FunctionType("toString", BuiltinStringType(), [BuiltinIntType()]),
]
