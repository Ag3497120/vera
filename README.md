# Vera

Vera は、日本語の文書から型付きの出来事を読み、根拠を示せる範囲で質問に答えるルールベースのツールです。読めない箇所や判断できない役割は、推測で埋めずに棄権します。主な入口はコマンドラインの round5 チャットと一問一答です。

## インストール

Python 環境で依存を入れ、公開リポジトリを編集可能モードでインストールします。

~~~sh
python -m pip install -r requirements.txt
python -m pip install -e .
~~~

## 文書への質問

文書ファイルまたは文書のあるフォルダーを指定して、チャットを起動します。

~~~sh
vera chat --mode round5 --document ./memo.txt
~~~

round5 を既定にする短い入口もあります。

~~~sh
vera-chat --document ./memo.txt
~~~

対話をせず一問だけ尋ねる場合:

~~~sh
vera ask "資料を渡したのは誰ですか。" --mode round5 --document ./memo.txt
~~~

CLI の挙動、入力の渡し方、返答の読み方は [チャットの使い方](docs/CHAT.md) を参照してください。

## できることと制約

- 文書に明記された日本語の出来事を、述語・項・否定などの構造として読みます。
- round5 は文書を付けた質問を処理します。根拠を確認できない場合は、型付きの棄権を返します。
- 粗い配置データベースはリポジトリに含めていません。手元の配置を使う場合は VERA_PLACEMENT で指定します。生成ツールは tools/build_coarse_placement.py、生成手順と入力条件は [粗い配置](docs/COARSE_PLACEMENT.md) を参照してください。
- 英語の粗い配置はありません。副詞と名詞句にかかる数量は読みません。で・に・へ・から の句がどの役割かは、型だけでは決まりません。
- コード、設計文書、テストは含みますが、隠し評価バンク、artifacts、attacks、results、配置 SQLite は配布物に含めません。

## 監査値

以下はチケットに記載された監査値です。評価方法は [EVAL.md](EVAL.md)、採点器の定義は [docs/BANK_SCORE.md](docs/BANK_SCORE.md) にあります。

- B1: 11/296、誤読 0
- B2: 0/286
- B5: 2/144
- B6: 0/132、誤ルート 0
- B7: 0/100、誤答 0、方針到達 0
- 質問の観測: 73/185、誤 0
- 攻撃 6 波の命中 35 件は、すべて修正済みまたは既知の穴として記録済み

## 設計文書

読解の契約は [READING_CONVENTIONS](docs/READING_CONVENTIONS.md) と [READING_SOUNDNESS](docs/READING_SOUNDNESS.md)、チャットは [CHAT](docs/CHAT.md)、配置の契約は [COARSE_PLACEMENT](docs/COARSE_PLACEMENT.md) を参照してください。その他の設計文書は docs/ にあります。
