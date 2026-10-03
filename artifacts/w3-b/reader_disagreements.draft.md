# (c) reader disagreements: draft table written by classify.py (the rule column is added by hand below the table)

## ja-032: 姉は妹より足が速い。
- expected: `[{"center": {"predicate": "速い", "polarity": "+", "tense": "nonpast", "modality": null, "voice": "active", "comparison": "comparative"}, "arms": {"entity": "姉", "standard": "妹", "attribute": "足"}}]`
- reader: `{"clauses": [{"predicate": "速い", "roles": {"entity": "姉", "standard": "妹"}, "polarity": "+", "tense": "nonpast", "modality": null, "voice": "active", "comparison": "comparative"}], "relations": []}`
- why: clause 0 arms differ

## ja-034: 東の畑は西の畑より水が多い。
- expected: `[{"center": {"predicate": "多い", "polarity": "+", "tense": "nonpast", "modality": null, "voice": "active", "comparison": "comparative"}, "arms": {"entity": "東の畑", "standard": "西の畑", "attribute": "水"}}]`
- reader: `{"clauses": [{"predicate": "多い", "roles": {"entity": "東の畑", "standard": "西の畑"}, "polarity": "+", "tense": "nonpast", "modality": null, "voice": "active", "comparison": "comparative"}], "relations": []}`
- why: clause 0 arms differ

## ja-037: 夏は冬より日が長い。
- expected: `[{"center": {"predicate": "長い", "polarity": "+", "tense": "nonpast", "modality": null, "voice": "active", "comparison": "comparative"}, "arms": {"entity": "夏", "standard": "冬", "attribute": "日"}}]`
- reader: `{"clauses": [{"predicate": "長い", "roles": {"entity": "夏", "standard": "冬"}, "polarity": "+", "tense": "nonpast", "modality": null, "voice": "active", "comparison": "comparative"}], "relations": []}`
- why: clause 0 arms differ

## ja-080: 先生が地図をぬめった。
- expected: `"unreadable"`
- reader: `{"clauses": [{"predicate": "ぬめる", "roles": {"agent": "先生", "patient": "地図"}, "polarity": "+", "tense": "past", "modality": null, "voice": "active"}], "relations": []}`
- why: expected unreadable, the reader read it

## ja-094: この橋はあの橋より長い。
- expected: `[{"center": {"predicate": "長い", "polarity": "+", "tense": "nonpast", "modality": null, "voice": "active", "comparison": "comparative"}, "arms": {"entity": "橋", "standard": "橋"}}]`
- reader: `{"clauses": [{"predicate": "長い", "roles": {"entity": "橋", "standard": "あの橋"}, "polarity": "+", "tense": "nonpast", "modality": null, "voice": "active", "comparison": "comparative"}], "relations": []}`
- why: clause 0 arms differ
