## 4. 測定結果（`artifacts/w10-f01/score_layer0.txt`・`score_layer1.txt` を機械で貼ったもの）

検査データの凍結: `data/FROZEN.json`・`freeze.txt`。LLM は `qwen3.8:27b-mlx`（Ollama）、配置は R8、入口は HTTP 経由（`scripts/run_eval.py`）。層 0 は `--max-tokens 200`（自由な答えの長さの上限。速度のため）、層 1 は文法が出力を縛る。


#### 層 0（既定） — `score_layer0.txt`

```
layers={0: 120} wrong=0 generated_only_answers=0 errors=0 missing=0
ONE   n=50 correct=21 wrong=0 missed=29
        missed  22  TESTIMONY|STRUCTURE_UNDETERMINED|QUESTION_NOT_READ
        missed   3  TESTIMONY|NO_RECORD|NO_ATTESTED_CELL
        missed   3  TESTIMONY|NO_RECORD|NO_TYPED_CANDIDATE
        missed   1  TESTIMONY|NO_RECORD|TYPE_EXCLUDED_ALL
NONE  n=50 correct=50 wrong=0 llm_called=50 testimony_shown=50 record_marked_sentences=0
CREATIVE n=20 constructed=20 abstained=0 wrong=0
latency vera_ms_llm_called       n=99 median=42.1 max=75.4
latency vera_ms_llm_not_called   n=21 median=39.1 max=165.3
latency llm_ms                   n=99 median=29223.6 max=42386.4
latency wall_ms                  n=120 median=26417.7 max=42428.7
```


#### 層 1（`--strict`） — `score_layer1.txt`

```
layers={1: 120} wrong=0 generated_only_answers=0 errors=0 missing=0
ONE   n=50 correct=18 wrong=0 missed=32
        missed  22  STRUCTURE_UNDETERMINED|STRUCTURE_UNDETERMINED|QUESTION_NOT_READ
        missed   3  NO_RECORD|NO_RECORD|NO_ATTESTED_CELL
        missed   3  STRUCTURE_UNDETERMINED|STRUCTURE_UNDETERMINED|NO_VERIFIABLE_ALTERNATIVE
        missed   3  NO_RECORD|NO_RECORD|NO_TYPED_CANDIDATE
        missed   1  NO_RECORD|NO_RECORD|TYPE_EXCLUDED_ALL
NONE  n=50 correct=50 wrong=0 llm_called=0 testimony_shown=0 record_marked_sentences=0
CREATIVE n=20 constructed=20 abstained=0 wrong=0
latency vera_ms_llm_called       n=38 median=9.2 max=183.0
latency vera_ms_llm_not_called   n=82 median=21.4 max=56.5
latency llm_ms                   n=38 median=5612.0 max=21811.5
latency wall_ms                  n=120 median=23.2 max=21819.8
```


### 4.1 `qwen3.5:4b`（第 2 ラウンドで追加。同じ検査データ・同じ入口・同じ採点。`score_q35_layer0.txt`・`score_q35_layer1.txt`）

手元の Ollama に後から加わった設計書の推奨モデル（§1.9 (c)）。`qwen3.8:27b-mlx` との比較は、上の表と下の表の同じ行を並べて読む。数値は測った出力そのもの。


#### qwen3.5:4b 層 0（既定） — `score_q35_layer0.txt`

```
layers={0: 120} wrong=0 generated_only_answers=0 errors=0 missing=0
ONE   n=50 correct=21 wrong=0 missed=29
        missed  22  TESTIMONY|STRUCTURE_UNDETERMINED|QUESTION_NOT_READ
        missed   3  TESTIMONY|NO_RECORD|NO_ATTESTED_CELL
        missed   3  TESTIMONY|NO_RECORD|NO_TYPED_CANDIDATE
        missed   1  TESTIMONY|NO_RECORD|TYPE_EXCLUDED_ALL
NONE  n=50 correct=50 wrong=0 llm_called=50 testimony_shown=50 record_marked_sentences=0
CREATIVE n=20 constructed=20 abstained=0 wrong=0
latency vera_ms_llm_called       n=99 median=56.2 max=115.9
latency vera_ms_llm_not_called   n=21 median=46.5 max=156.5
latency llm_ms                   n=99 median=7524.1 max=33690.2
latency wall_ms                  n=120 median=6417.4 max=33743.3
```


#### qwen3.5:4b 層 1（`--strict`） — `score_q35_layer1.txt`

```
layers={1: 120} wrong=0 generated_only_answers=0 errors=0 missing=0
ONE   n=50 correct=18 wrong=0 missed=32
        missed  22  STRUCTURE_UNDETERMINED|STRUCTURE_UNDETERMINED|QUESTION_NOT_READ
        missed   3  NO_RECORD|NO_RECORD|NO_ATTESTED_CELL
        missed   3  STRUCTURE_UNDETERMINED|STRUCTURE_UNDETERMINED|NO_VERIFIABLE_ALTERNATIVE
        missed   3  NO_RECORD|NO_RECORD|NO_TYPED_CANDIDATE
        missed   1  NO_RECORD|NO_RECORD|TYPE_EXCLUDED_ALL
NONE  n=50 correct=50 wrong=0 llm_called=0 testimony_shown=0 record_marked_sentences=0
CREATIVE n=20 constructed=20 abstained=0 wrong=0
latency vera_ms_llm_called       n=38 median=10.1 max=179.7
latency vera_ms_llm_not_called   n=82 median=27.2 max=68.1
latency llm_ms                   n=38 median=2723.6 max=5718.2
latency wall_ms                  n=120 median=35.3 max=5730.3
```


## 5. 応答の例（実際の応答。`eval_layer*.jsonl` から機械で選んで貼る。手で書き換えない）

選び方: (a) Q001 の層 0・層 1 の応答の全体、(b) 層 0 で outcome が TESTIMONY の応答のうち JSON が最も短いもの、(c) 層 0 の CONSTRUCTED のうち JSON が最も短いもの。


#### (a) Q001 `誰が地図を渡した？` — 層 0

```json
{
 "id": "chatcmpl-4c5c20818ddf4252b180618d82df003c",
 "object": "chat.completion",
 "created": 1791087935,
 "model": "qwen3.8:27b-mlx",
 "choices": [
  {
   "index": 0,
   "message": {
    "role": "assistant",
    "content": "太郎が地図を渡した。"
   },
   "finish_reason": "stop"
  }
 ],
 "usage": {},
 "vera": {
  "schema": "verantyx.fusion/1",
  "layer": 0,
  "request_kind": "factual",
  "reading": {
   "type": "QUESTION_CROSS",
   "state": "FILLED",
   "reason": "UNREAD_SENTENCES:11",
   "hole_role": "agent",
   "hole_type": [
    "GROUP_ORG",
    "PERSON"
   ],
   "filler": "太郎",
   "sources": [
    {
     "source": "F01.txt",
     "line": 1,
     "text": "太郎が地図を渡した。",
     "sentence_id": "F01.txt#1:1"
    }
   ]
  },
  "grammar": null,
  "grammar_id": null,
  "llm": {
   "called": false,
   "model": "qwen3.8:27b-mlx",
   "ok": null,
   "error": null,
   "raw": null,
   "withheld": false,
   "skipped_reason": "RECORD_ANSWERED"
  },
  "grammar_check": {
   "in_grammar": null,
   "reason": null
  },
  "provenance": [
   {
    "text": "太郎が地図を渡した。",
    "read": true,
    "mark": null,
    "unread_reason": null,
    "sentence_kind": "record",
    "origin": "record",
    "evidence": [
     "F01.txt#1:1"
    ],
    "arms": {
     "agent": {
      "surface": "太郎",
      "kind": "record",
      "evidence": [
       "F01.txt#1:1"
      ]
     },
     "patient": {
      "surface": "地図",
      "kind": "record",
      "evidence": [
       "F01.txt#1:1"
      ]
     }
    },
    "center_kind": "record",
    "via": "cross",
    "center": {
     "modality": null,
     "polarity": "+",
     "predicate": "渡す",
     "tense": "past",
     "voice": "active"
    }
   }
  ],
  "outcome": {
   "outcome": "ANSWER_HUMAN_BASIS",
   "content_shown": true,
   "reason": "RECORD_ANSWERED",
   "basis_policy": {
    "schema": "verantyx.basis_policy/1",
    "table_version": 1,
    "applied": true,
    "request_kind": "factual",
    "kind_class": "FACTUAL",
    "basis": "HUMAN",
    "basis_original": "HUMAN",
    "human_present": false,
    "show_reference": false,
    "outcome": "ANSWER_HUMAN_BASIS",
    "in_table": true,
    "counts": {
     "human": 1,
     "generated": 0,
     "non_evidence": 0,
     "request_text": 0,
     "unreadable": 0,
     "non_evidence_by_origin": {},
     "unknown_origin": 0,
     "unknown_origin_by_family": {},
     "unknown_origin_values": {}
    },
    "classify_version": 4,
    "confirm_id_version": 2,
    "sovereign": {
     "state": "UNKNOWN_NO_SOVEREIGN",
     "store_id": null,
     "records_read": 0,
     "rejected_by_user": 0,
     "confirmed_records_used": 0,
     "confirmed_records_not_used": 0,
     "ambiguous": false
    },
    "form": {
     "state": "UNKNOWN_NO_INDEX",
     "reasons": {
      "CAND_NOT_ONE_CROSS": 0,
      "CAND_CENTER_DIFFERS": 0,
      "CAND_ROLES_DIFFER": 0,
      "CAND_FILLER_SPAN_AMBIGUOUS": 0,
      "CAND_REREAD_DIFFERS": 0,
      "CAND_CONTENT_DIFFERS": 0
     },
     "families": {
      "local": "UNKNOWN_NO_INDEX",
      "pro": "UNKNOWN_NO_INDEX",
      "code": "UNKNOWN_NO_INDEX",
      "conversation": "UNKNOWN_NO_INDEX",
      "general_qa": "UNKNOWN_NO_INDEX",
      "code_qa": "UNKNOWN_NO_INDEX",
      "figurative_commonsense": "UNKNOWN_NO_INDEX",
      "narrative": "UNKNOWN_NO_INDEX",
      "paraphrase_entail": "UNKNOWN_NO_INDEX"
     },
     "searched_rows": 0,
     "candidates": 0,
     "distinct_forms": 0
    }
   }
  },
  "timing": {
   "vera_ms": 165.281,
   "llm_ms": 0.0
  }
 }
}
```


#### (a) Q001 `誰が地図を渡した？` — 層 1（`--strict`）

```json
{
 "id": "chatcmpl-e58ff153478e44df95cc27fdc7201d6d",
 "object": "chat.completion",
 "created": 1791090796,
 "model": "qwen3.8:27b-mlx",
 "choices": [
  {
   "index": 0,
   "message": {
    "role": "assistant",
    "content": "太郎が地図を渡した。"
   },
   "finish_reason": "stop"
  }
 ],
 "usage": {
  "prompt_tokens": 38,
  "completion_tokens": 17,
  "total_tokens": 55
 },
 "vera": {
  "schema": "verantyx.fusion/1",
  "layer": 1,
  "request_kind": "factual",
  "reading": {
   "type": "QUESTION_CROSS",
   "state": "FILLED",
   "reason": "UNREAD_SENTENCES:11",
   "hole_role": "agent",
   "hole_type": [
    "GROUP_ORG",
    "PERSON"
   ],
   "filler": "太郎",
   "sources": [
    {
     "source": "F01.txt",
     "line": 1,
     "text": "太郎が地図を渡した。",
     "sentence_id": "F01.txt#1:1"
    }
   ]
  },
  "grammar": {
   "id": "g-9457d9730c660c1f",
   "kind": "alternatives",
   "summary": {
    "alternatives_n": 1,
    "fillers": [
     "太郎"
    ],
    "predicate_forms": [
     "渡した"
    ],
    "dictionary_form": "渡す",
    "polarity": "+",
    "tense": "past",
    "sources": [
     "F01.txt#1:1"
    ],
    "sovereign": {
     "state": "NOT_CONFIGURED",
     "used_as_grammar_source": false,
     "reason": "SOVEREIGN_CLAIM_NOT_A_SENTENCE"
    }
   },
   "json_schema": {
    "type": "object",
    "properties": {
     "answer": {
      "type": "string",
      "enum": [
       "太郎が地図を渡した。"
      ]
     }
    },
    "required": [
     "answer"
    ],
    "additionalProperties": false
   },
   "gbnf": "root ::= alt0\nalt0 ::= \"太郎が地図を渡した。\"\n"
  },
  "grammar_id": "g-9457d9730c660c1f",
  "llm": {
   "called": true,
   "model": "qwen3.8:27b-mlx",
   "ok": true,
   "error": null,
   "raw": "{\n  \"answer\": \"太郎が地図を渡した。\"\n}",
   "withheld": false,
   "skipped_reason": null
  },
  "grammar_check": {
   "in_grammar": true,
   "reason": null
  },
  "provenance": [
   {
    "text": "太郎が地図を渡した。",
    "read": true,
    "mark": null,
    "unread_reason": null,
    "sentence_kind": "record",
    "origin": "record",
    "evidence": [
     "F01.txt#1:1"
    ],
    "arms": {
     "agent": {
      "surface": "太郎",
      "kind": "record",
      "evidence": [
       "F01.txt#1:1"
      ]
     },
     "patient": {
      "surface": "地図",
      "kind": "record",
      "evidence": [
       "F01.txt#1:1"
      ]
     }
    },
    "center_kind": "record",
    "via": "cross",
    "center": {
     "modality": null,
     "polarity": "+",
     "predicate": "渡す",
     "tense": "past",
     "voice": "active"
    }
   }
  ],
  "outcome": {
   "outcome": "ANSWER_HUMAN_BASIS",
   "content_shown": true,
   "reason": "ALL_SENTENCES_RECORD_HOLE_MATCHES",
   "basis_policy": {
    "schema": "verantyx.basis_policy/1",
    "table_version": 1,
    "applied": true,
    "request_kind": "factual",
    "kind_class": "FACTUAL",
    "basis": "HUMAN",
    "basis_original": "HUMAN",
    "human_present": false,
    "show_reference": false,
    "outcome": "ANSWER_HUMAN_BASIS",
    "in_table": true,
    "counts": {
     "human": 1,
     "generated": 0,
     "non_evidence": 0,
     "request_text": 0,
     "unreadable": 0,
     "non_evidence_by_origin": {},
     "unknown_origin": 0,
     "unknown_origin_by_family": {},
     "unknown_origin_values": {}
    },
    "classify_version": 4,
    "confirm_id_version": 2,
    "sovereign": {
     "state": "UNKNOWN_NO_SOVEREIGN",
     "store_id": null,
     "records_read": 0,
     "rejected_by_user": 0,
     "confirmed_records_used": 0,
     "confirmed_records_not_used": 0,
     "ambiguous": false
    },
    "form": {
     "state": "UNKNOWN_NO_INDEX",
     "reasons": {
      "CAND_NOT_ONE_CROSS": 0,
      "CAND_CENTER_DIFFERS": 0,
      "CAND_ROLES_DIFFER": 0,
      "CAND_FILLER_SPAN_AMBIGUOUS": 0,
      "CAND_REREAD_DIFFERS": 0,
      "CAND_CONTENT_DIFFERS": 0
     },
     "families": {
      "local": "UNKNOWN_NO_INDEX",
      "pro": "UNKNOWN_NO_INDEX",
      "code": "UNKNOWN_NO_INDEX",
      "conversation": "UNKNOWN_NO_INDEX",
      "general_qa": "UNKNOWN_NO_INDEX",
      "code_qa": "UNKNOWN_NO_INDEX",
      "figurative_commonsense": "UNKNOWN_NO_INDEX",
      "narrative": "UNKNOWN_NO_INDEX",
      "paraphrase_entail": "UNKNOWN_NO_INDEX"
     },
     "searched_rows": 0,
     "candidates": 0,
     "distinct_forms": 0
    }
   }
  },
  "timing": {
   "vera_ms": 182.951,
   "llm_ms": 3229.206
  }
 }
}
```


#### (b) Q011 `誰が電話を取った？` — 層 0、証言

```json
{
 "id": "chatcmpl-1d87816b2ebf46bf83e3c8e4fce5eb65",
 "object": "chat.completion",
 "created": 1791088108,
 "model": "qwen3.8:27b-mlx",
 "choices": [
  {
   "index": 0,
   "message": {
    "role": "assistant",
    "content": "［証言: LLM の答えです。記録の裏づけはありません］\n申し訳ありませんが、私はAIアシスタントであり、あなたの現実の生活や家庭内の状況（誰が電話に出たかなど）を知ることはできません。\n\nもし特定の文脈（例えば、小説の一場面、ニュース記事、あるいは特定の会話の記録など）に基づいて質問されている場合は、その背景やテキストを提供していただければ、お答えできるかもしれません。\n\n一般的な状況であれば、電話は通常、その時点で電話機やスマートフォンにアクセスできる家族や同居人、あるいは秘書などが取るものです。"
   },
   "finish_reason": "stop"
  }
 ],
 "usage": {
  "prompt_tokens": 18,
  "completion_tokens": 104,
  "total_tokens": 122
 },
 "vera": {
  "schema": "verantyx.fusion/1",
  "layer": 0,
  "request_kind": "factual",
  "reading": {
   "type": "STRUCTURE_UNDETERMINED",
   "state": "QUESTION_NOT_READ",
   "reason": "READER_ABSTAINED",
   "hole_role": null,
   "hole_type": null,
   "filler": null,
   "sources": []
  },
  "grammar": null,
  "grammar_id": null,
  "llm": {
   "called": true,
   "model": "qwen3.8:27b-mlx",
   "ok": true,
   "error": null,
   "raw": "申し訳ありませんが、私はAIアシスタントであり、あなたの現実の生活や家庭内の状況（誰が電話に出たかなど）を知ることはできません。\n\nもし特定の文脈（例えば、小説の一場面、ニュース記事、あるいは特定の会話の記録など）に基づいて質問されている場合は、その背景やテキストを提供していただければ、お答えできるかもしれません。\n\n一般的な状況であれば、電話は通常、その時点で電話機やスマートフォンにアクセスできる家族や同居人、あるいは秘書などが取るものです。",
   "withheld": false,
   "skipped_reason": null
  },
  "grammar_check": {
   "in_grammar": null,
   "reason": null
  },
  "provenance": [
   {
    "text": "申し訳ありませんが、私はAIアシスタントであり、あなたの現実の生活や家庭内の状況（誰が電話に出たかなど）を知ることはできません。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:UNREAD_SPAN:interrogative source does not assert a fact",
    "sentence_kind": "testimony",
    "origin": "testimony",
    "evidence": [],
    "arms": {},
    "center_kind": "testimony",
    "via": null,
    "source": {
     "family": "llm",
     "origin": "testimony",
     "model": "qwen3.8:27b-mlx"
    }
   },
   {
    "text": "もし特定の文脈（例えば、小説の一場面、ニュース記事、あるいは特定の会話の記録など）に基づいて質問されている場合は、その背景やテキストを提供していただければ、お答えできるかもしれません。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:UNREAD_SPAN:interrogative source does not assert a fact",
    "sentence_kind": "testimony",
    "origin": "testimony",
    "evidence": [],
    "arms": {},
    "center_kind": "testimony",
    "via": null,
    "source": {
     "family": "llm",
     "origin": "testimony",
     "model": "qwen3.8:27b-mlx"
    }
   },
   {
    "text": "一般的な状況であれば、電話は通常、その時点で電話機やスマートフォンにアクセスできる家族や同居人、あるいは秘書などが取るものです。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "testimony",
    "origin": "testimony",
    "evidence": [],
    "arms": {},
    "center_kind": "testimony",
    "via": null,
    "source": {
     "family": "llm",
     "origin": "testimony",
     "model": "qwen3.8:27b-mlx"
    }
   }
  ],
  "outcome": {
   "outcome": "TESTIMONY",
   "content_shown": true,
   "reason": "NO_RECORD_ANSWER:STRUCTURE_UNDETERMINED",
   "basis_policy": {
    "schema": "verantyx.basis_policy/1",
    "table_version": 1,
    "applied": true,
    "request_kind": "factual",
    "kind_class": "FACTUAL",
    "basis": "NONE",
    "basis_original": "NONE",
    "human_present": false,
    "show_reference": false,
    "outcome": "ABSTAIN",
    "in_table": true,
    "counts": {
     "human": 0,
     "generated": 0,
     "non_evidence": 3,
     "request_text": 0,
     "unreadable": 0,
     "non_evidence_by_origin": {
      "testimony": 3
     },
     "unknown_origin": 0,
     "unknown_origin_by_family": {},
     "unknown_origin_values": {}
    },
    "classify_version": 4,
    "confirm_id_version": 2,
    "sovereign": {
     "state": "UNKNOWN_NO_SOVEREIGN",
     "store_id": null,
     "records_read": 0,
     "rejected_by_user": 0,
     "confirmed_records_used": 0,
     "confirmed_records_not_used": 0,
     "ambiguous": false
    },
    "form": {
     "state": "NOT_ATTEMPTED_OUTCOME"
    }
   }
  },
  "timing": {
   "vera_ms": 48.28,
   "llm_ms": 18350.744
  }
 }
}
```


#### (c) Q119 `「旅人は山を越えた。」を言い換えて。` — 層 0、構成

```json
{
 "id": "chatcmpl-30b7c3d2fdff48bdaf6f130d579b501d",
 "object": "chat.completion",
 "created": 1791090775,
 "model": "qwen3.8:27b-mlx",
 "choices": [
  {
   "index": 0,
   "message": {
    "role": "assistant",
    "content": "［構成: 事実の主張ではありません］\n文書 [F05.txt:6] に記載されている「旅人は山を越えた。」を言い換えると、例えば以下のような表現になります。\n\n*   旅人は山を登った。\n*   旅人は山を越えて向こう側へ行った。\n*   旅人は山脈を通過した。"
   },
   "finish_reason": "stop"
  }
 ],
 "usage": {
  "prompt_tokens": 576,
  "completion_tokens": 71,
  "total_tokens": 647
 },
 "vera": {
  "schema": "verantyx.fusion/1",
  "layer": 0,
  "request_kind": "paraphrase",
  "reading": {
   "type": "RECORDS",
   "state": null,
   "reason": null,
   "hole_role": null,
   "hole_type": null,
   "filler": null,
   "sources": []
  },
  "grammar": null,
  "grammar_id": null,
  "llm": {
   "called": true,
   "model": "qwen3.8:27b-mlx",
   "ok": true,
   "error": null,
   "raw": "文書 [F05.txt:6] に記載されている「旅人は山を越えた。」を言い換えると、例えば以下のような表現になります。\n\n*   旅人は山を登った。\n*   旅人は山を越えて向こう側へ行った。\n*   旅人は山脈を通過した。",
   "withheld": false,
   "skipped_reason": null
  },
  "grammar_check": {
   "in_grammar": null,
   "reason": null
  },
  "provenance": [
   {
    "text": "文書 [F05.txt:6] に記載されている「旅人は山を越えた。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:UNREAD_SPAN:uninterpreted colon scope",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   },
   {
    "text": "」を言い換えると、例えば以下のような表現になります。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   },
   {
    "text": "*   旅人は山を登った。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   },
   {
    "text": "*   旅人は山を越えて向こう側へ行った。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   },
   {
    "text": "*   旅人は山脈を通過した。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   }
  ],
  "outcome": {
   "outcome": "CONSTRUCTED",
   "content_shown": true,
   "reason": "NON_FACTUAL_REQUEST",
   "basis_policy": {
    "schema": "verantyx.basis_policy/1",
    "table_version": 1,
    "applied": true,
    "request_kind": "paraphrase",
    "kind_class": "NON_FACTUAL",
    "basis": "HUMAN",
    "basis_original": "HUMAN",
    "human_present": false,
    "show_reference": false,
    "outcome": "CONSTRUCTED",
    "in_table": true,
    "counts": {
     "human": 32,
     "generated": 0,
     "non_evidence": 0,
     "request_text": 0,
     "unreadable": 0,
     "non_evidence_by_origin": {},
     "unknown_origin": 0,
     "unknown_origin_by_family": {},
     "unknown_origin_values": {}
    },
    "classify_version": 4,
    "confirm_id_version": 2,
    "sovereign": {
     "state": "NOT_CONSULTED",
     "store_id": null,
     "records_read": 0,
     "rejected_by_user": 0,
     "confirmed_records_used": 0,
     "confirmed_records_not_used": 0,
     "ambiguous": false
    },
    "form": {
     "state": "NOT_ATTEMPTED_OUTCOME"
    }
   }
  },
  "timing": {
   "vera_ms": 16.361,
   "llm_ms": 9361.32
  }
 }
}
```
