import py

try:
    from rpython.rtyper.test.test_llinterp import interpret
except ImportError:
    pytestmark = py.test.mark.skip("Needs RPython to be on the PYTHONPATH")

from rply import LexerGenerator, ParserGenerator, Token
from rply.errors import ParserGeneratorWarning

from .base import BaseTests
from .utils import BoxInt, ParserState


class BaseTestTranslation(BaseTests):
    def test_basic_lexer(self):
        lg = LexerGenerator()
        lg.add("NUMBER", r"\d+")
        lg.add("PLUS", r"\+")

        l = lg.build()

        def f(n):
            tokens = l.lex("%d+%d+%d" % (n, n, n))
            i = 0
            s = 0
            while i < 5:
                t = tokens.next()
                if i % 2 == 0:
                    if t.name != "NUMBER":
                        return -1
                    s += int(t.value)
                else:
                    if t.name != "PLUS":
                        return -2
                    if t.value != "+":
                        return -3
                i += 1

            ended = False
            try:
                tokens.next()
            except StopIteration:
                ended = True

            if not ended:
                return -4

            return s

        assert self.run(f, [14]) == 42

    def test_stacked_lexer(self):
        lg = LexerGenerator()
        lg.add('NUMBER', r'\d+')
        lg.add('ADD', r'\+')
        lg.add('COMMENT_START', r'\(#', transition='push', target='comment')

        lg.ignore(r'\s+')

        comment = lg.add_state('comment')
        comment.add('COMMENT_START', r'\(#', transition='push', target='comment')
        comment.add('COMMENT_END', r'#\)', transition='pop')
        comment.add('COMMENT', r'([^(#]|#(?!\))|\)(?!#))+')

        l = lg.build()

        def f():
            stream = l.lex('(# this is (# a nested comment #)#) 1 + 1 (# 1 # 1 #)')
            t = stream.next()
            if t.name != 'COMMENT_START':
                return -1
            if t.value != '(#':
                return -2
            t = stream.next()
            if t.name != 'COMMENT':
                return -3
            if t.value != ' this is ':
                return -4
            t = stream.next()
            if t.name != 'COMMENT_START':
                return -5
            if t.value != '(#':
                return -6
            t = stream.next()
            if t.name != 'COMMENT':
                return -7
            if t.value != ' a nested comment ':
                return -8
            t = stream.next()
            if t.name != 'COMMENT_END':
                return -9
            if t.value != '#)':
                return -10
            t = stream.next()
            if t.name != 'COMMENT_END':
                return -11
            if t.value != '#)':
                return -12
            t = stream.next()
            if t.name != 'NUMBER':
                return -13
            if t.value != '1':
                return -14
            t = stream.next()
            if t.name != 'ADD':
                return -15
            if t.value != '+':
                return -16
            t = stream.next()
            if t.name != 'NUMBER':
                return -17
            if t.value != '1':
                return -18
            t = stream.next()
            if t.name != 'COMMENT_START':
                return -19
            if t.value != '(#':
                return -20
            t = stream.next()
            if t.name != 'COMMENT':
                return -21
            if t.value != ' 1 # 1 ':
                return -22
            t = stream.next()
            if t.name != 'COMMENT_END':
                return -23
            if t.value != '#)':
                return -24
            try:
                stream.next()
            except StopIteration:
                pass
            else:
                return -25
            return 0

        assert self.run(f, []) == 0

    def test_basic_parser(self):
        pg = ParserGenerator(["NUMBER", "PLUS"])

        @pg.production("main : expr")
        def main(p):
            return p[0]

        @pg.production("expr : expr PLUS expr")
        def expr_op(p):
            return BoxInt(p[0].getint() + p[2].getint())

        @pg.production("expr : NUMBER")
        def expr_num(p):
            return BoxInt(int(p[0].getstr()))

        with self.assert_warns(
            ParserGeneratorWarning, "1 shift/reduce conflict"
        ):
            parser = pg.build()

        def f(n):
            return parser.parse(iter([
                Token("NUMBER", str(n)),
                Token("PLUS", "+"),
                Token("NUMBER", str(n))
            ])).getint()

        assert self.run(f, [12]) == 24

    def test_parser_state(self):
        pg = ParserGenerator(["NUMBER", "PLUS"], precedence=[
            ("left", ["PLUS"]),
        ])

        @pg.production("main : expression")
        def main(state, p):
            state.count += 1
            return p[0]

        @pg.production("expression : expression PLUS expression")
        def expression_plus(state, p):
            state.count += 1
            return BoxInt(p[0].getint() + p[2].getint())

        @pg.production("expression : NUMBER")
        def expression_number(state, p):
            state.count += 1
            return BoxInt(int(p[0].getstr()))

        parser = pg.build()

        def f():
            state = ParserState()
            return parser.parse(iter([
                Token("NUMBER", "10"),
                Token("PLUS", "+"),
                Token("NUMBER", "12"),
                Token("PLUS", "+"),
                Token("NUMBER", "-2"),
            ]), state=state).getint() + state.count

        assert self.run(f, []) == 26


class TestTranslation(BaseTestTranslation):
    def run(self, func, args):
        return interpret(func, args)


class TestUntranslated(BaseTestTranslation):
    def run(self, func, args):
        return func(*args)
