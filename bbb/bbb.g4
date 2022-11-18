grammar bbb;

basic_binary_buffer :
	hash_
	(whitespace+ member)+
	whitespace*
	EOF
;

//32 hex chars
hash_ :
	hex_digit hex_digit hex_digit hex_digit
		hex_digit hex_digit hex_digit hex_digit
		hex_digit hex_digit hex_digit hex_digit
		hex_digit hex_digit hex_digit hex_digit
		hex_digit hex_digit hex_digit hex_digit
		hex_digit hex_digit hex_digit hex_digit
		hex_digit hex_digit hex_digit hex_digit
		hex_digit hex_digit hex_digit hex_digit
;

whitespace :
	space
	| newline
	| tab
;

member :
	member_name whitespace* colon whitespace* type_
	| at_sign hash_
;

member_name :
	specific_name
	| underscore
;

specific_name :
	(lower_alpha | upper_alpha | decimal_digit)
		(lower_alpha | decimal_digit | underscore)*
;

type_ :
	underscore
	| aggregate_type (whitespace* range_)? whitespace* open_brace whitespace*
			member (whitespace+ member)* whitespace*
		close_brace
	| base_type (whitespace* range_)?
;

/*
'struct' | 'enum' | 'union'
*/
aggregate_type :
	(Char_s Char_t Char_r Char_u Char_c Char_t) | (Char_e Char_n Char_u Char_m) | (Char_u Char_n Char_i Char_o Char_n)
;

range_ :
	(open_bracket | open_paren) whitespace*
		canon_natural_num whitespace*
		(comma whitespace* canon_natural_num whitespace*)?
	(close_bracket | close_paren)
;

/*
0 | [1-9][0-9]*
*/
canon_natural_num :
	Char_0
	| (Char_1 | Char_2 | Char_3 | Char_4 | Char_5 | Char_6 | Char_7 | Char_8 | Char_9)
		(Char_0 | Char_1 | Char_2 | Char_3 | Char_4 | Char_5 | Char_6 | Char_7 | Char_8 | Char_9)*
;

/*
'u1' | 'u8' | 'u16' | 'u32' | 'u64'
	| 'i8' | 'i16' | 'i32' | 'i64'
*/
base_type :
	(Char_u Char_1) | (Char_u Char_8) | (Char_u Char_1 Char_6) | (Char_u Char_3 Char_2) | (Char_u Char_6 Char_4) | (Char_i Char_8) | (Char_i Char_1 Char_6) | (Char_i Char_3 Char_2) | (Char_i Char_6 Char_4)
;

//building block rules

/*
[0-9]
*/
decimal_digit :
	Char_0 | Char_1 | Char_2 | Char_3 | Char_4 | Char_5 | Char_6 | Char_7 | Char_8 | Char_9
;

/*
[0-9a-f]
*/
hex_digit :
	Char_0 | Char_1 | Char_2 | Char_3 | Char_4 | Char_5 | Char_6 | Char_7 | Char_8 | Char_9 | Char_a | Char_b | Char_c | Char_d | Char_e | Char_f
;

/*
[a-z]
*/
lower_alpha :
	Char_a | Char_b | Char_c | Char_d | Char_e | Char_f | Char_g | Char_h | Char_i | Char_j | Char_k | Char_l | Char_m | Char_n | Char_o | Char_p | Char_q | Char_r | Char_s | Char_t | Char_u | Char_v | Char_w | Char_x | Char_y | Char_z
;

/*
[A-Z]
*/
upper_alpha :
	Char_A | Char_B | Char_C | Char_D | Char_E | Char_F | Char_G | Char_H | Char_I | Char_J | Char_K | Char_L | Char_M | Char_N | Char_O | Char_P | Char_Q | Char_R | Char_S | Char_T | Char_U | Char_V | Char_W | Char_X | Char_Y | Char_Z
;

//simplest tokens

open_brace : Open_brace;
Open_brace : '{';

close_brace : Close_brace;
Close_brace : '}';

open_bracket : Open_bracket;
Open_bracket : '[';

close_bracket : Close_bracket;
Close_bracket : ']';

open_paren : Open_paren;
Open_paren : '(';

close_paren : Close_paren;
Close_paren : ')';

at_sign : At_sign;
At_sign : '@';

colon : Colon;
Colon : ':';

comma : Comma;
Comma : ',';

newline : Newline;
Newline : '\n';

space : Space;
Space : ' ';

tab : Tab;
Tab : '\t';

underscore : Underscore;
Underscore : '_';

Char_0 : '0';
Char_1 : '1';
Char_2 : '2';
Char_3 : '3';
Char_4 : '4';
Char_5 : '5';
Char_6 : '6';
Char_7 : '7';
Char_8 : '8';
Char_9 : '9';
Char_A : 'A';
Char_B : 'B';
Char_C : 'C';
Char_D : 'D';
Char_E : 'E';
Char_F : 'F';
Char_G : 'G';
Char_H : 'H';
Char_I : 'I';
Char_J : 'J';
Char_K : 'K';
Char_L : 'L';
Char_M : 'M';
Char_N : 'N';
Char_O : 'O';
Char_P : 'P';
Char_Q : 'Q';
Char_R : 'R';
Char_S : 'S';
Char_T : 'T';
Char_U : 'U';
Char_V : 'V';
Char_W : 'W';
Char_X : 'X';
Char_Y : 'Y';
Char_Z : 'Z';
Char_a : 'a';
Char_b : 'b';
Char_c : 'c';
Char_d : 'd';
Char_e : 'e';
Char_f : 'f';
Char_g : 'g';
Char_h : 'h';
Char_i : 'i';
Char_j : 'j';
Char_k : 'k';
Char_l : 'l';
Char_m : 'm';
Char_n : 'n';
Char_o : 'o';
Char_p : 'p';
Char_q : 'q';
Char_r : 'r';
Char_s : 's';
Char_t : 't';
Char_u : 'u';
Char_v : 'v';
Char_w : 'w';
Char_x : 'x';
Char_y : 'y';
Char_z : 'z';
