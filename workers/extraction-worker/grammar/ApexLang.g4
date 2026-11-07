grammar ApexLang;

document
    : declaration* EOF
    ;

declaration
    : IDENTIFIER declarationName? LPAREN declarationBody RPAREN
    ;

declarationName
    : IDENTIFIER
    | NUMBER
    ;

declarationBody
    : (declaration | property | expressionToken)*
    ;

property
    : IDENTIFIER COLON LBRACE declarationBody RBRACE
    | IDENTIFIER COLON propertyValue
    | IDENTIFIER LBRACE declarationBody RBRACE
    | IDENTIFIER declarationName? LBRACE declarationBody RBRACE
    ;

propertyValue
    : (STRING | NUMBER | IDENTIFIER | REFERENCE | RAW_BLOCK | SYMBOL)+
    ;

expressionToken
    : STRING
    | NUMBER
    | IDENTIFIER
    | REFERENCE
    | RAW_BLOCK
    | SYMBOL
    ;

LPAREN: '(';
RPAREN: ')';
LBRACE: '{';
RBRACE: '}';
COLON: ':';
REFERENCE: '@' [A-Za-z0-9_./-]+;
NUMBER: [+-]? [0-9]+ ('.' [0-9]+)? ([eE] [+-]? [0-9]+)?;
STRING
    : '\'' ('\'\'' | ~'\'')* '\''
    | '"' ('""' | ~'"')* '"'
    ;
RAW_BLOCK
    : '~~~' .*? '~~~'
    | '```' .*? '```'
    ;
IDENTIFIER: [A-Za-z_] [A-Za-z0-9_.-]*;
LINE_COMMENT: ('//' | '--') ~[\r\n]* -> skip;
BLOCK_COMMENT: '/*' .*? '*/' -> skip;
WS: [ \t\r\n]+ -> skip;
SYMBOL: .;
