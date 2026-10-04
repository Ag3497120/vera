# 計画ソブリン（store_id plan）

このディレクトリには sovereign の実体（sqlite・registry）が作られるが、コミットしない（`.gitignore`）。
registry はファイルの **絶対パス** を持つので、複製すると複製元のファイルを読み書きしてしまう（W8-shadow の指示書 P1）。
各ツリーで `python tools/ops/plan_ingest.py` が `ops/decisions/*.md` から作る。履歴の正本は git 上の `ops/decisions/*.md`。
道具は registry の示すファイルが `<root>/stores/plan.sqlite` でなければ `PLAN_SOVEREIGN_PATH_ELSEWHERE` で止まる。
監査役が「sqlite もコミットする」と裁定しても、registry の絶対パスの問題が残る（統合先は `PLAN_SOVEREIGN_PATH_ELSEWHERE` で止まる）ので、`.gitignore` を外すだけでは足りない。
影運用の間、Vera はこのソブリンに書かない（道具は子プロセスの環境から VERA_SOVEREIGN_* を消し、--confirm を渡さない）。
