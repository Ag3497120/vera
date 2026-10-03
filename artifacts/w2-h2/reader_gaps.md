# 読めなかった単位（読解器の側への入力）

出典: `tests/routing_from_text/reader_gaps.py` の出力（`reader_gaps.json`）。単位は `segment` の切り方による。

- e1: 9 単位。UNREAD 9
  - UNREAD/NO_SUPPORTED_CLAUSE: 7
  - UNREAD/QUANTIFIER_NOT_MAPPED: 1
  - UNREAD/UNREAD_SPAN: 1
- e2: 13 単位。UNREAD 13
  - UNREAD/NO_PREDICATE_TOKEN: 5
  - UNREAD/NO_SUPPORTED_CLAUSE: 6
  - UNREAD/UNREAD_SPAN: 2
- e3: 10 単位。UNREAD 10
  - UNREAD/NO_PREDICATE_TOKEN: 3
  - UNREAD/NO_SUPPORTED_CLAUSE: 7
- e4: 13 単位。UNREAD 13
  - UNREAD/NO_PREDICATE_TOKEN: 4
  - UNREAD/NO_SUPPORTED_CLAUSE: 5
  - UNREAD/PREDICATE_VALUE_NOT_MAPPED: 1
  - UNREAD/UNREAD_SPAN: 2
  - UNREAD/UNSUPPORTED_CLAUSE: 1
- e5: 10 単位。MAPPED 1 UNREAD 9
  - UNREAD/EN_UNREAD: 9
- e6: 10 単位。UNREAD 10
  - UNREAD/EN_UNREAD: 8
  - UNREAD/UNKNOWN_PREDICATE: 2
- r1: 8 単位。MAPPED 7 COMPARISON_ONLY 1
- r2: 6 単位。MAPPED 6

## 理由別の合計と例

- UNREAD/NO_SUPPORTED_CLAUSE: 25（例: ミズチは手が速く、普段の実装はミズチに任せる。）
- UNREAD/EN_UNREAD: 17（例: We run four agents.）
- UNREAD/NO_PREDICATE_TOKEN: 12（例: ## エージェントの分担）
- UNREAD/UNREAD_SPAN: 5（例: テストを書く仕事はミズチでもカガリでもよく、どちらを優先するかは決めていない。）
- UNREAD/UNKNOWN_PREDICATE: 2（例: Routing notes）
- UNREAD/PREDICATE_VALUE_NOT_MAPPED: 1（例: コマとユキは別の会社なので、独立性は問題ない。）
- UNREAD/QUANTIFIER_NOT_MAPPED: 1（例: うちのチームでは三つのエージェントを使い分けている。）
- UNREAD/UNSUPPORTED_CLAUSE: 1（例: ・「小さい子」と書いたらコマのこと。）
