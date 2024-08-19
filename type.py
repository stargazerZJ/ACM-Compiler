from antlr4 import ParserRuleContext
from syntax_error import MxSyntaxError


class TypeBase:
    name: str
    members: dict[str, "TypeBase"]
    ir_name: str = None

    def __init__(self, name: str, ir_name: str = None):
        self.name = name
        self.members = {}
        self.ir_name = ir_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TypeBase):
            return self.name == other.name
        return False

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def add_member(self, name: str, typ: "TypeBase", ctx: ParserRuleContext = None):
        if name in self.members:
            raise MxSyntaxError(f"Type '{self.name}' already has a member named '{name}'", ctx)
        self.members[name] = typ

    def get_member(self, name: str, ctx: ParserRuleContext = None) -> "TypeBase":
        if name in self.members:
            return self.members[name]
        raise MxSyntaxError(f"Type '{self.name}' has no member named '{name}'", ctx)

    def call(self, param_types: list["TypeBase"], ctx: ParserRuleContext = None) -> "TypeBase":
        raise MxSyntaxError(f"Type '{self.name}' cannot be called as a function", ctx)

    def subscript(self, ctx: ParserRuleContext = None) -> "TypeBase":
        raise MxSyntaxError(f"Type '{self.name}' cannot be subscripted", ctx)

    def can_be_null(self, ctx: ParserRuleContext = None) -> bool:
        return True

    def internal_type(self) -> "TypeBase":
        return self

    def is_array(self) -> bool:
        return False


class FunctionType(TypeBase):
    ret_type: TypeBase
    param_types: list[TypeBase]

    def __init__(self, name: str, ret_type: TypeBase, param_types: list[TypeBase], ir_name: str = None):
        ir_name = ir_name or "@" + name
        super().__init__(name, ir_name)
        self.ret_type = ret_type
        self.param_types = param_types

    def call(self, param_types: list[TypeBase], ctx: ParserRuleContext = None) -> TypeBase:
        if len(param_types) != len(self.param_types):
            raise MxSyntaxError(
                f"Function call error: expected {len(self.param_types)} parameters, got {len(param_types)}", ctx)
        for expected, actual in zip(self.param_types, param_types):
            if expected != actual:
                if actual == builtin_types["null"]:
                    if not expected.can_be_null(ctx):
                        raise MxSyntaxError(
                            f"Function call error: expected parameter of type {expected.name}, got null", ctx)
                else:
                    raise MxSyntaxError(
                        f"Function call error: expected parameter of type {expected.name}, got {actual.name}", ctx)
        return self.ret_type


class ArrayType(TypeBase):
    element_type: TypeBase
    dimension: int

    def __init__(self, element_type: TypeBase, dimension: int):
        super().__init__(f"{element_type.name}" + "[]" * dimension, "%.arr")
        self.element_type = element_type
        self.dimension = dimension
        self.add_member("size", FunctionType("size", BuiltinIntType(), [], "invalid"))

    def subscript(self, ctx: ParserRuleContext = None) -> TypeBase:
        if self.dimension == 1:
            return self.element_type
        return ArrayType(self.element_type, self.dimension - 1)

    def internal_type(self) -> TypeBase:
        return InternalPtrType(self)

    def is_array(self) -> bool:
        return True


class BuiltinIntType(TypeBase):
    def __init__(self):
        super().__init__("int", "i32")

    def can_be_null(self, ctx: ParserRuleContext = None) -> bool:
        return False


class BuiltinBoolType(TypeBase):
    def __init__(self):
        super().__init__("bool", "i1")

    def can_be_null(self, ctx: ParserRuleContext = None) -> bool:
        return False


class BuiltinVoidType(TypeBase):
    def __init__(self):
        super().__init__("void", "void")


class BuiltinStringType(TypeBase):
    def __init__(self):
        super().__init__("string")
        self.add_member("length", FunctionType("length", BuiltinIntType(), [], "@string.length"))
        self.add_member("substring",
                        FunctionType("substring", self, [BuiltinIntType(), BuiltinIntType()], "@string.substring"))
        self.add_member("parseInt", FunctionType("parseInt", BuiltinIntType(), [], "@string.parseInt"))
        self.add_member("ord", FunctionType("ord", BuiltinIntType(), [BuiltinIntType()], "@string.ord"))

    def can_be_null(self, ctx: ParserRuleContext = None) -> bool:
        return False

    def internal_type(self) -> TypeBase:
        return InternalPtrType(self)


class BuiltinNullType(TypeBase):
    def __init__(self):
        super().__init__("null", "ptr")

    def internal_type(self) -> TypeBase:
        return InternalPtrType(self)


class ClassType(TypeBase):
    def __init__(self, name: str):
        super().__init__(name, "%class." + name)

    def internal_type(self) -> TypeBase:
        return InternalPtrType(self)


class InternalPtrType(TypeBase):
    """Internal type for pointers"""
    pointed_to: TypeBase

    def __init__(self, pointed_to: TypeBase = None):
        super().__init__("ptr", "ptr")
        self.pointed_to = pointed_to

    def is_array(self) -> bool:
        return self.pointed_to.is_array()


builtin_types = {
    "int": BuiltinIntType(),
    "bool": BuiltinBoolType(),
    "void": BuiltinVoidType(),
    "string": BuiltinStringType(),
    "null": BuiltinNullType(),  # a special type for null literal
}
builtin_functions = {
    "print": FunctionType("print", builtin_types["void"], [builtin_types["string"]]),
    "println": FunctionType("println", builtin_types["void"], [builtin_types["string"]]),
    "printInt": FunctionType("printInt", builtin_types["void"], [builtin_types["int"]]),
    "printlnInt": FunctionType("printlnInt", builtin_types["void"], [builtin_types["int"]]),
    "getString": FunctionType("getString", builtin_types["string"], []),
    "getInt": FunctionType("getInt", builtin_types["int"], []),
    "toString": FunctionType("toString", builtin_types["string"], [builtin_types["int"]]),
}

internal_functions = {
    "string.length": builtin_types["string"].members["length"],
    "string.substring": builtin_types["string"].members["substring"],
    "string.parseInt": builtin_types["string"].members["parseInt"],
    "string.ord": builtin_types["string"].members["ord"],
    "malloc": FunctionType("malloc", InternalPtrType(builtin_types["int"]), [builtin_types["int"]]),
    # array.size is always inlined, so we don't need to define it here
}

for elem_type in ["int", "bool", "ptr", "arr_ptr"]:
    for dimension in [1, 2]:
        name = f"__new_{elem_type}_{dimension}d_array__"
        internal_functions[name] = FunctionType(name, InternalPtrType(builtin_types["null"]),
                                                [builtin_types["int"]] * dimension)
