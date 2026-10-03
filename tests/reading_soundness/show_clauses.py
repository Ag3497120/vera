#!/usr/bin/env python3
"""文を読解器(document_view)と検査(license_clause)に通し、節・役割・unsupported の理由・検査の結果を 1 行ずつ出す。
使い方: PYTHONPATH=<木> python show_clauses.py <文を 1 行 1 文で書いたファイル>   (英語は --en: en_frames.read_typed の結果)
隔離検査: 読み込んだ verantyx* が PYTHONPATH の木の配下であること(外れていれば終了コード 2)。
"""
import os, sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    english = '--en' in sys.argv
    lines = [l.strip() for l in open(args[0], encoding='utf-8').read().split('\n') if l.strip()]
    if english:
        from verantyx import en_frames as en
        for text in lines:
            typed = getattr(en, 'read_typed', None)           # dev (075d486) has only read()
            frame, why = typed(text) if typed else (en.read(text), ())
            print(('READ ' if frame else 'NONE ') + text, '->', (en.key(frame) if frame else list(why)))
    else:
        from verantyx.semantic_reader import document_view
        from verantyx.semantic_verify import license_clause
        from verantyx import constructions
        constructions.discover()
        for text in lines:
            view = document_view({'d': text})
            print('##', text)
            if not view.clauses:
                print('   (no clauses)', [u.reason for u in view.unread])
            for c in view.clauses:
                try:
                    license_clause(c, view); lic = 'PASS'
                except Exception as exc:
                    lic = 'REJ:' + str(exc)
                roles = [(r.name, r.span.text if r.rule not in ('comparison_direction', 'comparison_dimension') else '<' + str(r.term) + '>') for r in c.roles]
                print('  ', 'SUP' if not c.unsupported else 'uns', c.rule, c.predicate, c.polarity, roles, list(c.unsupported), lic)
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root + ' foreign_modules=' + str(foreign))
    sys.exit(2 if foreign else 0)


if __name__ == '__main__':
    main()
