parser grammar MxParser;

options {
    tokenVocab = MxLexer;
}


file_Input: (function_Definition | class_Definition | variable_Definition | ';')* EOF  ;


/* Function part. */
function_Definition : function_Argument '(' function_Param_List? ')' block_Stmt;
function_Param_List : function_Argument (',' function_Argument)*;
function_Argument   : typename Identifier;

/* Class part.  */
class_Definition    : 'class' Identifier '{'
    (variable_Definition | function_Definition | class_Ctor_Function)*
    '}' ';';
class_Ctor_Function : Identifier '(' ')' block_Stmt;

/* Basic statement.  */
stmt:
    simple_Stmt         |
    branch_Stmt         |
    loop_Stmt           |
    flow_Stmt           |
    variable_Definition |
    block_Stmt          ;
block_Stmt  : '{' stmt* '}' ;
simple_Stmt : expression? ';';
suite : block_Stmt | stmt ;


/* Branch part. */
branch_Stmt: if_Stmt else_if_Stmt* else_Stmt?   ;
if_Stmt     : 'if'      '(' expression ')' suite ;
else_if_Stmt: 'else if' '(' expression ')' suite ;
else_Stmt   : 'else'                       suite ;


/* Loop part */
loop_Stmt   : for_Stmt | while_Stmt ;
for_Stmt    :
    'for' '('
        (initializer = expression? ';' | variable_Definition)
        condition   = expression? ';'
        step        = expression?
    ')' suite;
while_Stmt  : 'while' '(' condition = expression ')' suite  ;


/* Flow control. */
flow_Stmt: ('continue' | 'break' | ('return' expression?)) ';';


/* Variable part. */
variable_Definition :
    typename init_Stmt (',' init_Stmt)* ';';
init_Stmt: Identifier ('=' (array_Literal | expression))?;


/* Expression part */
expr_List   : expression (',' expression)*   ;
expression  :
  '(' l = expression    op = ')'                                        # bracket
    | l = expression   (op = '['    sub += expression  ']')+            # subscript
    | l = expression    op = '('    expr_List?  ')'                     # function
    | l = expression    op = '.'    Identifier                          # member
    | l = expression    op = ('++' |'--')                               # unary
    |                   op = 'new'  new_Type                            # construct
    | <assoc = right>   op = ('++' | '--' )             r = expression  # unary
    | <assoc = right>   op = ('+'  | '-'  | '~' | '!' ) r = expression  # unary
    | l = expression    op = ('*'  | '/'  | '%')        r = expression  # binary
    | l = expression    op = ('+'  | '-'  )             r = expression  # binary
    | l = expression    op = ('<<' | '>>' )             r = expression  # binary
    | l = expression    op = ('<=' | '>=' | '<' | '>')  r = expression  # binary
    | l = expression    op = ('==' | '!=' )             r = expression  # binary
    | l = expression    op = '&'    r = expression                      # binary
    | l = expression    op = '^'    r = expression                      # binary
    | l = expression    op = '|'    r = expression                      # binary
    | l = expression    op = '&&'   r = expression                      # binary
    | l = expression    op = '||'   r = expression                      # binary
    | <assoc = right>   cond = expression  op = '?'    l = expression ':'  r = expression # ternary
    | <assoc = right>   l = expression  op = '='    r = expression      # binary
    | f_string                                                          # fstring
    | literal_Constant                                                  # literal
    | Identifier                                                        # atom
    | This                                                              # this;


/* F-string part. */
f_string: (FStringHead (expression FStringMid)*? expression FStringTail) | FStringAtom;


/* Basic part.  */
typename            : (BasicTypes | Identifier) ('[' ']')* ;
new_Type :
    (BasicTypes new_Index)
    | (BasicTypes ('[' ']')+ array_Literal?)
    | (Identifier new_Index? ('(' ')')?) ;
new_Index           : ('[' good+=expression ']')+ ('[' ']')* ('[' bad+=expression ']')*;
array_Literal : '{' (literal_List | array_Literal_List )? '}' ;
array_Literal_List : array_Literal (',' array_Literal)* ;
literal_List  : literal_Constant (',' literal_Constant)* ;
literal_Constant    : Number | Cstring | Null | True_ | False_;

