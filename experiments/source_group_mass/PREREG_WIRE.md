# 事前登録 — is_junk_core を candidates_for_query の直接ヒット経路に配線する(2026-09-02、配線前に凍結)
変更: consensus_store.candidates_for_query の variants ループで、is_junk_core(v) なら候補に入れない。
      追記経路(:730)には既にある。帯(direction_band)には**掛けない**(junk_gate B で棄却済み)。
判定線: FORKS_ALL       vera lab が 178/178 のまま(skipped 0)
        GUARD_UNCHANGED experiments/guard/verify_all.py の forks 89/89、測定は環境依存2件(凍結バイナリ)以外不変
        HARNESS_MATCH   run_reach 経路の raw 腕が、配線後は A2 の raw+門 と同じ数(36/224/40)になる
落ちたら配線を戻す(git)。通っても 20 件の「法令条文の特定性」は未解決のまま、と明記する。
