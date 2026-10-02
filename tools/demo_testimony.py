"""Exercise testimony/evidence boundaries in typed memory without external agents."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from verantyx.conductor import ProjectFrame
from verantyx.memory_frame import Memory, WriteRejected, check_witness


def _closed_choice(prompt: str, target: str) -> str:
    """Choose only the requested item from the options shown by Resolver."""
    options = re.findall(r"(?m)^(\d+): (.*)$", prompt)
    index = next(int(i) for i, option in options if option == target)
    return json.dumps({"choice": index})


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="vera-testimony-") as temp:
        root = Path(temp)
        memory_path = root / "memory.jsonl"
        hash_path = root / "hashed-source.txt"
        text_path = root / "text-source.txt"
        subjects = ["ルーター", "メール", "サーバー", "タスク", "メモ", "ユーザー"]
        hash_path.write_text("demo source\n", encoding="utf-8")

        sentence = f"{subjects[1]}の未読上限は20件である。"
        text_path.write_text(sentence + "\n", encoding="utf-8")
        digest = hashlib.sha256(hash_path.read_bytes()).hexdigest()
        commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
                                capture_output=True, text=True).stdout.strip()
        command = [sys.executable, "-B", "-c", "raise SystemExit(0)"]
        command_result = subprocess.run(command, check=False, capture_output=True)
        assert command_result.returncode == 0

        memory = Memory(str(memory_path), asker=lambda prompt: _closed_choice(prompt, "ルーター"))
        witnesses = [
            ("file_hash", {"kind": "file_hash", "path": str(hash_path), "sha256": digest}),
            ("text_in_file", {"kind": "text_in_file", "path": str(text_path), "needle": sentence}),
            ("git_commit", {"kind": "git_commit", "repo": str(Path.cwd()), "commit": commit}),
            ("command_result", {"kind": "command_result", "command": command,
                                 "exit_code": command_result.returncode, "expected_exit": 0}),
            ("testimony", {"kind": "testimony", "by": "human witness"}),
            ("constructed", {"kind": "constructed", "source": "demo constructed input"}),
        ]
        records = []
        for subject, (witness_class, witness) in zip(subjects, witnesses):
            records.append(memory.write("FACT", f"demo-{witness_class}", witness=witness,
                                        subject=subject, attribute="未読上限", value="20件"))

        assert check_witness(witnesses[0][1]) == "FRESH"
        assert check_witness(witnesses[1][1]) == "FRESH"
        assert check_witness(witnesses[2][1]) == "FRESH"
        assert check_witness(witnesses[3][1]) == "FRESH"

        evidence_classes = {"file_hash", "text_in_file", "git_commit", "command_result"}
        for subject, (witness_class, _), record in zip(subjects, witnesses, records):
            question = f"{subject}の未読上限は？"
            answer = memory.ask(question)
            assert answer["verdict"] == "ANSWER"
            assert answer["values"] == ["20件"]
            assert answer["witness_classes"] == {record["id"]: witness_class}
            evidence_answer = memory.ask(question, evidence_only=True)
            if witness_class in evidence_classes:
                assert evidence_answer["verdict"] == "ANSWER"
                assert evidence_answer["witness_classes"] == {record["id"]: witness_class}
            else:
                assert evidence_answer["verdict"] != "ANSWER"
                assert record["id"] not in evidence_answer["witness_classes"]

        for kind, slots in (
            ("FACT", {"subject": "生成事実", "attribute": "状態", "value": "完了"}),
            ("DECISION", {"subject": "生成判断", "choice": "案一"}),
            ("INVARIANT", {"subject": "生成条件", "rule": "推測しない"}),
        ):
            mislabeled = {"kind": "file_hash", "path": str(hash_path), "sha256": digest,
                          "generated": True, **slots}
            try:
                memory.write(kind, "generated-output", witness=mislabeled, **slots)
            except WriteRejected:
                pass
            else:
                raise AssertionError(f"{kind} accepted generated output as file evidence")

        frame = ProjectFrame(memory)
        canonical, alias_ids = frame._resolve_option("未知語", "demo closed-choice alias")
        assert canonical == "ルーター"
        alias_record = memory.records[alias_ids[0]]
        alias_event = memory.aliases[("agent-option", "未知語")]
        assert len(alias_event["asks"]) == 2
        assert alias_event["support"] == "testimony"
        assert alias_record["witness"]["kind"] == "testimony"
        alias_question = f"{alias_record['slots']['subject']}の語義対応は？"
        alias_answer = memory.ask(alias_question)
        assert alias_answer["verdict"] == "ANSWER"
        assert alias_answer["witness_classes"][alias_record["id"]] == "testimony"
        alias_evidence_answer = memory.ask(alias_question, evidence_only=True)
        assert alias_evidence_answer["verdict"] != "ANSWER"

    print("DEMO OK")


if __name__ == "__main__":
    main()
