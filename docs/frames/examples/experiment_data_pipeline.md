# Example conduct frame: preprocessing pipeline for experiment measurement data.
# Mixes Japanese action names to check that frames are not limited to English.

[goal]
project: SpectraPrep
statement: The pipeline turns raw spectrometer files into normalised tables and records every discarded sample with its reason

[philosophy_invariants]
I1: Raw measurement files are never modified
I2: A discarded sample is listed with a reason and never silently dropped
I3: Normalisation constants come from the calibration file and never from the data being normalised

[completion_criteria]
C1: The unit tests for the normaliser pass | {"kind":"command_exit","command":["python","-m","pytest","tests/test_normalise.py","-q"],"expected_exit":0}
C2: The discard report lists the fixture rejects | {"kind":"text_in_file","path":"out/discard_report.txt","needle":"sample_017 rejected"}
C3: The calibration owner reviews the constants | human-judged

[phases]
P1: Read the raw files
P2: Normalise with the calibration constants
P3: Write tables and the discard report

[phase_order]
P1 -> P2: Normalisation needs parsed samples
P2 -> P3: Reports follow normalised values

[decisions]
D1: output format => The tables are written as csv
D2: SCOPE | raw file edits | out of scope
D3: CHOICE | 欠測の扱い | 理由つき除外

[vocabulary_aliases]
欠測 => missing sample
校正 => calibration

[escalation_conditions]
E1: calibration drift => The calibration owner must judge a drifting reference => human => ANY

[protected_actions]
delete => Human approval is required before removing any file => human
生データの移動 => 生データを動かす前に人の承認が必要 => human

[write_allowlist]
W1: pipeline
W2: tests/preprocessing
W3: out

[forbidden_actions]
生データの書き換え => 原データは証拠であり承認があっても変更できない
overwrite calibration file => The calibration file is owned by the instrument team

[conflict_precedence]
R1: forbidden_actions > philosophy_invariants: The hard prohibition is read first when an invariant is ambiguous
R2: philosophy_invariants > completion_criteria: A passing check never outranks the invariants
R3: completion_criteria > protected_actions: A met criterion does not unlock a protected operation, and an unmet one does not require it

[agent_settings]
claude_model: claude-opus-5-5
claude_effort: max
