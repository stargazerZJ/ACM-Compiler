from mxc.frontend.ir_generation.block_chain import BlockChain
from mxc.common.ir_repr import BBExit
from mxc.frontend.semantic.syntax_recorder import FunctionInfo
from mxc.frontend.semantic.type import InternalPtrType


class BuilderStack:
    layers: list["Layer"]
    this_type: InternalPtrType | None
    current_function: FunctionInfo | None

    class Layer:
        chain: BlockChain
        is_loop: bool
        breaks: list[BBExit]
        continues: list[BBExit]

        def __init__(self, chain: BlockChain, is_loop: bool):
            self.chain = chain
            self.is_loop = is_loop
            if is_loop:
                self.breaks = []
                self.continues = []

    def __init__(self):
        self.layers = []
        self.this_type = None

    def push(self, chain: BlockChain, is_loop: bool = False):
        self.layers.append(BuilderStack.Layer(chain, is_loop))

    def pop(self):
        layer = self.layers.pop()
        if layer.is_loop:
            return layer.breaks, layer.continues

    def top(self) -> Layer:
        return self.layers[-1]

    def top_chain(self) -> BlockChain:
        return self.top().chain

    def collect_breaks(self, breaks: list[BBExit]):
        for layer in reversed(self.layers):
            if layer.is_loop:
                layer.breaks.extend(breaks)
                return
        raise AssertionError("Break outside loop")

    def collect_continues(self, continues: list[BBExit]):
        for layer in reversed(self.layers):
            if layer.is_loop:
                layer.continues.extend(continues)
                return
        raise AssertionError("Continue outside loop")

    def continue_exits(self):
        return self.top().continues

    def break_exits(self):
        return self.top().breaks

    def enter_class_scope(self, class_type: InternalPtrType):
        self.this_type = class_type

    def exit_class_scope(self):
        self.this_type = None

    def get_this_type(self):
        return self.this_type

    def enter_function(self, function: FunctionInfo):
        self.current_function = function

    def exit_function(self):
        self.current_function = None

    def get_current_function(self):
        return self.current_function
