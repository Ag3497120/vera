import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
ad = [r for r in rows if r['status'] == 'ADOPTED']
L = ["# P4 目視の記録（目視であり正解データではない。第 3 ラウンド。裁定 A・B の後）", "",
     "採用された候補: %d 件（下の「採用の目視」）。誤採用（目視）の件数は下に書いた。以下は全 %d 穴の一覧（`p4_real.jsonl` から機械で生成）。「申告の型が穴の語の型か」= 申告の型が、配置が穴の語に与える型（`hole_word_types`）に入るか（—: 配置が穴の語に型を与えない、または申告が無い）。" % (len(ad), len(rows)), "",
     "| 文 | 穴 | 申告の型 | 穴の語の配置の型 | 申告の型が穴の語の型か | 近い語[最初に落ちた門] | 理由 |", "|---|---|---|---|---|---|---|"]
for r in rows:
    words = '; '.join('%s[%s]' % (g['word'], g['gate']) for g in r['gate_log'])
    v = r.get('declared_type_is_a_type_of_the_word')
    L.append('| %s | %s:%s | %s | %s | %s | %s | %s |' % (r['text'], r['hole']['particle'], r['hole']['head'], (r['declaration'] or {}).get('type'), ','.join(r.get('hole_word_types') or []) or '—',
                                                      {True: 'はい', False: 'いいえ', None: '—'}[v], words or '（語なし）', r['reason']))
L += ["", "## 採用の目視（人が見た判定。正解データではない）", ""]
for r in ad:
    L.append("- 「%s」 穴 %s:%s → 候補 `%s`、申告の型 %s（穴の語の配置の型 %s）。判定欄は実装役が目視で下に書く。" % (r['text'], r['hole']['particle'], r['hole']['head'], r['candidate'], r['declaration']['type'], ','.join(r['hole_word_types'])))
if not ad:
    L.append("- 採用 0 件: 目視の対象は無い。誤採用（目視）= 0 件（採用が無いので 0。正解データによる確認ではない）。")
L += ["", "## 門 (a4) で止まった語（r2 では (a1)〜(a3) を通り、後の門に任された語）", ""]
for r in rows:
    for g in r['gate_log']:
        if g['gate'] == 'a4':
            L.append("- 「%s」 穴 %s:%s → 候補 `%s`、申告の型 %s、穴の語の配置の型 %s、型ごとの役割 %s、理由 %s%s" % (r['text'], r['hole']['particle'], r['hole']['head'], g['word'], (r['declaration'] or {}).get('type'), ','.join(g['hole_word_types']) or '—',
                     json.dumps(g['role_by_type'], ensure_ascii=False), g['reason'], (' (%s)' % g['split_kind']) if g.get('split_kind') else ''))
L += ["", "`GATE_D_TIE` の行は複数の語がすべての門を通ったために棄権した行（同点は棄権）。`NO_CANDIDATE_WORDS` は後段が近い語を 1 つも返さなかった行（後段の失敗ではない。型つきの不採用）。"]
open(sys.argv[2], 'w').write('\n'.join(L) + '\n')
