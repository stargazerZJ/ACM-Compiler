from antlr4 import ParserRuleContext


class Renamer:
    """Rename variables, functions, etc. in IR"""
    name_map: dict[str, int]

    def __init__(self):
        self.name_map = {}

    def get_name(self, name: str = None) -> str:
        name = name if name is not None else "tmp"
        if name not in self.name_map:
            self.name_map[name] = 1
            return name
        self.name_map[name] += 1
        name = f"{name}.{self.name_map[name]}"
        return self.get_name(name)

    def get_name_from_ctx(self, name: str, ctx: ParserRuleContext) -> str:
        if name not in self.name_map:
            self.name_map[name] = 1
            return name
        name += f".line{ctx.start.line}"
        return self.get_name(name)

    def register_name(self, name: str):
        assert name not in self.name_map
        self.name_map[name] = 1


renamer: Renamer = Renamer()


def reset_renamer():
    global renamer
    renamer = Renamer()
