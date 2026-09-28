# codex_sentences_ja.jsonl.gz — Japanese sentences generated for Vera

- About 1.16 million distinct Japanese sentences (one JSON object per line: `text`, `scene`, `angle`).
- Written by OpenAI Codex (models gpt-6-sol and gpt-6-luna, September 2026) on request, scene by scene (台所, 市場, 図書館, … about 1,200 scenes, each from several angles such as a child's eye). Each batch passed a 4-layer gate against programmatic generation (no templates, no enumerations).
- Used by Vera only as a source of counts: an event becomes knowledge when two or more independent batches wrote it. Nothing is trained on it.
- Not reviewed sentence by sentence. It may contain mistakes and odd phrasing.
- Terms: the generated text is distributed by the repository owner, who reviewed the provider's terms of use. Check them yourself before using the data to train models.
