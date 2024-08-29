# Generated from MxParser.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .MxParser import MxParser
else:
    from MxParser import MxParser

# This class defines a complete generic visitor for a parse tree produced by MxParser.

class MxParserVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by MxParser#file_Input.
    def visitFile_Input(self, ctx:MxParser.File_InputContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#function_Definition.
    def visitFunction_Definition(self, ctx:MxParser.Function_DefinitionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#function_Param_List.
    def visitFunction_Param_List(self, ctx:MxParser.Function_Param_ListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#function_Argument.
    def visitFunction_Argument(self, ctx:MxParser.Function_ArgumentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#class_Definition.
    def visitClass_Definition(self, ctx:MxParser.Class_DefinitionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#class_Ctor_Function.
    def visitClass_Ctor_Function(self, ctx:MxParser.Class_Ctor_FunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#stmt.
    def visitStmt(self, ctx:MxParser.StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#block_Stmt.
    def visitBlock_Stmt(self, ctx:MxParser.Block_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#simple_Stmt.
    def visitSimple_Stmt(self, ctx:MxParser.Simple_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#suite.
    def visitSuite(self, ctx:MxParser.SuiteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#branch_Stmt.
    def visitBranch_Stmt(self, ctx:MxParser.Branch_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#if_Stmt.
    def visitIf_Stmt(self, ctx:MxParser.If_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#else_if_Stmt.
    def visitElse_if_Stmt(self, ctx:MxParser.Else_if_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#else_Stmt.
    def visitElse_Stmt(self, ctx:MxParser.Else_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#loop_Stmt.
    def visitLoop_Stmt(self, ctx:MxParser.Loop_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#for_Stmt.
    def visitFor_Stmt(self, ctx:MxParser.For_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#while_Stmt.
    def visitWhile_Stmt(self, ctx:MxParser.While_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#flow_Stmt.
    def visitFlow_Stmt(self, ctx:MxParser.Flow_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#variable_Definition.
    def visitVariable_Definition(self, ctx:MxParser.Variable_DefinitionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#init_Stmt.
    def visitInit_Stmt(self, ctx:MxParser.Init_StmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#expr_List.
    def visitExpr_List(self, ctx:MxParser.Expr_ListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#subscript.
    def visitSubscript(self, ctx:MxParser.SubscriptContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#fstring.
    def visitFstring(self, ctx:MxParser.FstringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#binary.
    def visitBinary(self, ctx:MxParser.BinaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#function.
    def visitFunction(self, ctx:MxParser.FunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#bracket.
    def visitBracket(self, ctx:MxParser.BracketContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#this.
    def visitThis(self, ctx:MxParser.ThisContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#member.
    def visitMember(self, ctx:MxParser.MemberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#construct.
    def visitConstruct(self, ctx:MxParser.ConstructContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#unary.
    def visitUnary(self, ctx:MxParser.UnaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#atom.
    def visitAtom(self, ctx:MxParser.AtomContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#ternary.
    def visitTernary(self, ctx:MxParser.TernaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#literal.
    def visitLiteral(self, ctx:MxParser.LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#f_string.
    def visitF_string(self, ctx:MxParser.F_stringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#typename.
    def visitTypename(self, ctx:MxParser.TypenameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#new_Type.
    def visitNew_Type(self, ctx:MxParser.New_TypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#new_Index.
    def visitNew_Index(self, ctx:MxParser.New_IndexContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#array_Literal.
    def visitArray_Literal(self, ctx:MxParser.Array_LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#array_Literal_List.
    def visitArray_Literal_List(self, ctx:MxParser.Array_Literal_ListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#literal_List.
    def visitLiteral_List(self, ctx:MxParser.Literal_ListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MxParser#literal_Constant.
    def visitLiteral_Constant(self, ctx:MxParser.Literal_ConstantContext):
        return self.visitChildren(ctx)



del MxParser