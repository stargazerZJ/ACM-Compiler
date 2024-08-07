from antlr4.error.ErrorListener import ErrorListener


class MxSyntaxError(Exception):
    """Exception raised for syntax errors in the Mx* compiler."""

    def __init__(self, message, ctx=None):
        self.message = message
        if ctx is not None:
            self.line_number = ctx.start.line
            self.column_number = ctx.start.column
        else:
            self.line_number = None
            self.column_number = None
        super().__init__(self.message)

    def __str__(self):
        location_info = ""
        if self.line_number is not None and self.column_number is not None:
            location_info = f" at line {self.line_number}, column {self.column_number}"
        elif self.line_number is not None:
            location_info = f" at line {self.line_number}"
        return f"{self.message}{location_info}"


class ThrowingErrorListener(ErrorListener):
    def __init__(self):
        super(ThrowingErrorListener, self).__init__()

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        error_message = f"Syntax error: {msg}"
        error = MxSyntaxError(error_message)
        error.line_number = line
        error.column_number = column
        raise error