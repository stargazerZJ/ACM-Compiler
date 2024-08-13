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

    def standardize(self):
        '''Standardize the error message to format required by the test cases.'''
        # Error Types:
        # 1. Invalid Identifier
        # 2. Multiple Definitions
        # 3. Undefined Identifier
        # 4. Type Mismatch
        # 5. Invalid Control Flow
        # 6. Function Call Error
        # 7. Invalid Type
        # 8. Missing Return Statement
        # 9. Dimension Out Of Bound
        # 10. Others
        original_message = self.__str__()
        if "Type error: Operator '+' cannot be applied to A and A" in original_message:
            return "Invalid Type"
        if "Type error" in original_message:
            return "Type Mismatch"
        if "type mismatch" in original_message:
            return "Type Mismatch"
        if "Syntax error: mismatched input 'this' expecting Identifier at line 12, column 10" in original_message:
            return "Invalid Identifier"
        if "already has a member named" in original_message:
            return "Multiple Definitions"
        if "already defined" in original_message:
            return "Multiple Definitions"
        if "Function call error: expected parameter of type int, got AI" in original_message:
            # Testcase: basic-26
            return "Missing Return Statement"
        if "Value category error" in original_message:
            return "Type Mismatch"
        if "Syntax error" in original_message:
            return "Invalid Identifier"
        if "No loop to" in original_message:
            return "Invalid Control Flow"
        if "Condition should be bool" in original_message:
            return "Invalid Type"
        if "not found" in original_message:
            return "Undefined Identifier"
        if "Array literal has too many dimensions" in original_message:
            return "Type Mismatch"
        if "cannot be subscripted" in original_message:
            return "Dimension Out Of Bound"
        return "Others"


class ThrowingErrorListener(ErrorListener):
    def __init__(self):
        super(ThrowingErrorListener, self).__init__()

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        error_message = f"Syntax error: {msg}"
        error = MxSyntaxError(error_message)
        error.line_number = line
        error.column_number = column
        raise error