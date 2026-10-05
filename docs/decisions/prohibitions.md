<!-- ops-meta {"schema": "vera.ops.decision/1", "source": "/Users/motonisihikoudai/Projects/vera-impl/wt/W8-shadow-S/AGENTS.md", "source_lines": "10-14,29-38", "source_sha256": "bc4608e18fc6e6feaaeaca6ea6d304e5a134806ce6b9d60159bdec5923bc3c5e", "copied_at": "2026-10-04 09:25:48 +0900", "copied_by": "implementer", "sections": {"## 場所と権限": "auditor", "## 守る原則（破ると不合格）": "auditor"}} -->
## 場所と権限
- 作業場所は **指定された開発ツリーのクローン**（このファイルのあるディレクトリ）だけ。
- 読み取り専用: `/Users/motonisihikoudai/vera-wiring`、`/Users/motonisihikoudai/vera-codex-corpus`、`/Users/motonisihikoudai/Projects/vera`。
- **開かない**: `/Users/motonisihikoudai/Projects/vera-impl/hidden`（評価バンク）、ほかのチケットのクローン（`/Users/motonisihikoudai/Projects/vera-impl/wt/*`）。
- `git commit` / `git push` はしない（コミットは監査役が行う）。ネットワークを使わない（チケットが本物の LLM の起動を明示的に許可した場合だけ、その上限の中で使う）。
- 配置・索引などツリーの外の実体（`/Users/motonisihikoudai/Projects/vera-impl/build/`）は読むだけ。作り直すのはチケットが指示したときだけ。

## 守る原則（破ると不合格）
- **同点は棄権する**。順序・辞書順・ハッシュ順で勝者を作らない。
- **束ねず重ねる**。別種の信号を一票にまとめず、一段の出力を次段へ手渡す。系列をまたいで票を合算しない。
- **分からないことと偽であることを混ぜない**。「無い」「索引が無い」「読めない」「決まらない」は別々の型で返す。
- **構成したもの・生成物・LLM の返答は証拠ではない**。型で申告する（`constructed` / `generated` / `testimony`）。事実の主張の根拠は人が書いた出所だけ。
- **自動で解決・棄却・読み飛ばしたものも数えて記録する**。見えない解決は嘘。
- **削除しない**。修理は規則を直し、データを手で消さない。退役は追記。既存の試験の期待を変えるときは、監査役の許可の範囲で、名前を変えず、前後の全文を docs に残す。
- **実測のない数値を書かない**。文書・コメント・報告の数値には測定出力のファイルを添える。
- **語の一覧を足して直さない**。表層の規則の追加で直すと、新しい文で別の穴が開くことが実測済み（W1-a4、攻撃の第 1 波）。直せないときは **その構成を棄権に倒す**。
- テスト入力のハードコード、既存テストの削除・skip／xfail 化・期待値の弱体化をしない。
- 新しい能力は既定の入口（CLI / 公開 API）から到達できること。
