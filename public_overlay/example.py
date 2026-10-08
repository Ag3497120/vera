import vera_base
chat = vera_base.Chat([{"title": "営業案内", "ja": "当店の営業時間は午前10時から午後7時までです。定休日は毎週水曜日です。"}], tree=True)
for q in ["こんにちは", "定休日はいつですか。", "猫とは何ですか", "「猫」でダジャレを作って。", "18＋6はいくつですか。", "春の俳句を作って"]:
    print(q, "→", chat.reply(q)["text"])
