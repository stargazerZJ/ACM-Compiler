lexer grammar MxLexer;

channels {
    COMMENTS
}


/* Comments */
Comment_Multi   : '/*'.*?'*/'             -> channel(COMMENTS)  ;
Comment_Single  : '//'.*? (NewLine | EOF) -> channel(COMMENTS)  ;


/* Basics */
NewLine : ('\r' | '\n' | '\u2028' | '\u2029')           -> skip ;
Blank   : (' ' | '\t' | '\u000B' | '\u000C' | '\u00A0') -> skip ;

/* Basic types. */
BasicTypes  : 'int' | 'bool' | 'void' | 'string' ;


/* Built-in Variables */
This    : 'this'  ;
Null    : 'null'  ;
True_    : 'true'  ;
False_   : 'false' ;


/* Classes. */
New     : 'new'   ;
Class   : 'class' ;


/* Flow. */
Else_if     : 'else if'    ;
If          : 'if'         ;
Else        : 'else'       ;
For         : 'for'        ;
While       : 'while'      ;
Break       : 'break'      ;
Continue    : 'continue'   ;
Return      : 'return'     ;


/* Uniary operators. */
Increment   : '++'  ;
Decrement   : '--'  ;
Logic_Not   : '!'   ;
Bit_Inv     : '~'   ;


/* Uniary or binary operators. */
Add : '+'   ;
Sub : '-'   ;


/* Binary operators. */
Dot         : '.'   ;
Mul         : '*'   ;
Div         : '/'   ;
Mod         : '%'   ;
Shift_Right : '>>'  ;
Shift_Left_ : '<<'  ;
Cmp_le      : '<='  ;
Cmp_ge      : '>='  ;
Cmp_lt      : '<'   ;
Cmp_gt      : '>'   ;
Cmp_eq      : '=='  ;
Cmp_ne      : '!='  ;
Bit_And     : '&'   ;
Bit_Xor     : '^'   ;
Bit_Or_     : '|'   ;
Logic_And   : '&&'  ;
Logic_Or_   : '||'  ;
Assign      : '='   ;


/* Ternary operators. */
Quest       : '?'   ;
Colon       : ':'   ;

/* Strings */
FStringHead : 'f"' (FStringChar | DualDollar)* '$' ;
FStringMid  : '$' (FStringChar | DualDollar)* '$' ;
FStringTail : '$' (FStringChar | DualDollar)* '"' ;
FStringAtom : 'f"' (FStringChar | DualDollar)* '"' ;
fragment FStringChar : EscapeChar | ~('$' | '"' ) ;
fragment DualDollar: '$$';
Cstring : '"' (EscapeChar | .)*? '"' ;
fragment EscapeChar: '\\\\' | '\\n' | '\\t' | '\\"';

/* Brackets */
Paren_Left_ : '('   ;
Paren_Right : ')'   ;
Brack_Left_ : '['   ;
Brack_Right : ']'   ;
Brace_Left_ : '{'   ;
Brace_Right : '}'   ;
Comma       : ','   ;
Semi_Colon  : ';'   ;


/* Others */
Number          : [1-9] Digit* | '0';
fragment Digit  : [0-9] ;
Identifier      : [A-Za-z][A-Za-z_0-9]*;

