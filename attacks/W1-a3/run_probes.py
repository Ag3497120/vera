"""Run the hand-written W1-a3 sentence probes as separate CLI invocations."""
import json
import os
import subprocess
from pathlib import Path


TREE = Path(__file__).resolve().parents[2]
PYTHON = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
OUT = Path(__file__).with_name("probe_outputs.jsonl")

JA = """妹がパンを焼いた。
妹がパンを焼く。
兄が水を飲んだ。
兄が水を飲む。
母は窓を閉めた。
母は窓を閉める。
父が新聞を読んだ。
父が新聞を読む。
猫が魚を食べた。
猫が魚を食べる。
先生が問題を説明した。
先生が図を描いた。
友人が荷物を運んだ。
母が鍵を見つけた。
兄が電気を消した。
妹が歌を歌った。
鳥が枝を飛び越えた。
選手が山に登った。
犬が庭を走った。
子犬が骨をかじった。
妹はパンを焼かない。
妹はパンを焼かなかった。
兄は水を飲まない。
兄は水を飲まなかった。
母は窓を閉めない。
母は窓を閉めなかった。
父は新聞を読まない。
父は新聞を読まなかった。
猫は魚を食べない。
猫は魚を食べなかった。
先生は問題を説明しない。
先生は問題を説明しなかった。
友人は荷物を運ばない。
友人は荷物を運ばなかった。
兄は電気を消さない。
兄は電気を消さなかった。
妹は歌を歌わない。
妹は歌を歌わなかった。
表が画家によって描かれた。
図が研究者によって作られた。
要約が編集者によって書かれた。
英語が講師によって教えられた。
青色が審査員によって選ばれた。
総会が委員会によって延期された。
目次が出版社に更新された。
倉庫が大工に改装された。
図が姉に描かれた。
兄が姉に叱られた。
妹が兄に褒められた。
弟が姉に噛まれた。
犬が飼い主に追いかけられた。
会議が中止された。
図表が修正された。
庭が荒らされた。
妹は弟に絵を見せた。
先生は生徒に課題を与えた。
母が娘に花を贈った。
兄が妹に帽子を買った。
姉が弟に本を渡した。
父は母に料理を作ってあげた。
妹が友人に写真を送ってくれた。
弟は姉に作文を直してもらった。
母は私に部屋を片づけてくれた。
妹が弟にケーキを作った。
友人から小包が届いた。
子どもが先生に質問した。
先生が来られた。
部長が話された。
会長が資料を読まれた。
先生が生徒に説明された。
牧師が友人に励まされた。
本が読まれた。
要約が読まれた。
表が見られた。
倉庫が見つけられた。
昔の海岸が思い返された。
昔の庭が思い起こされた。
妹は電話をしなかった。
ふと昔の海岸が思い返された。
自転車が細道を駆け抜けた。""".splitlines()

EN = """Mia opened the box.
Mia opens the box.
He closed the door.
He closes the door.
The dog chased the ball.
The dog chases the ball.
She helped Ben.
Ben praised Mia.
I finished the report.
They repaired the chair.
We moved the table.
The teacher explained the rule.
The student answered Mia.
The guard stopped the car.
The cook prepared dinner.
Mia did not open the box.
He did not close the door.
The dog did not chase the ball.
She did not help Ben.
Ben did not praise Mia.
I did not finish the report.
They did not repair the chair.
We did not move the table.
The teacher did not explain the rule.
The student did not answer Mia.
The guard did not stop the car.
The cook did not prepare dinner.
The cat did not watch the bird.
The clerk did not mail a letter.
The child did not carry a bag.
The box was opened by Mia.
The door was closed by him.
The ball was chased by the dog.
Ben was praised by Mia.
The report was finished by me.
The chair was repaired by them.
The table was moved by us.
The rule was explained by the teacher.
Mia was helped by the student.
The car was stopped by the guard.
Dinner was prepared by the cook.
A letter was mailed to Ben by the clerk.
Mia gave Ben a key.
Ben sent Mia a note.
The clerk mailed Mia a package.
The teacher showed Ben a map.
The doctor offered Mia advice.
Mia gave the teacher a book.
Ben sent the teacher a photo.
The child handed Mia a toy.
The manager assigned Ben a task.
The cook served Mia lunch.
Mia can open the box.
He is opening the door.
The dog has chased the ball.
She may help Ben.
The teacher should explain the rule.
Every student opened a box.
Mia opened the box yesterday.
Because Mia opened the box, Ben smiled.""".splitlines()


def main():
    assert len(JA) == 80, len(JA)
    assert len(EN) == 60, len(EN)
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(TREE), "PYTHONDONTWRITEBYTECODE": "1"})
    rows = []
    for lang, sentences in (("ja", JA), ("en", EN)):
        for i, sentence in enumerate(sentences, 1):
            command = [PYTHON, "-m", "verantyx.semantic_read", "--text=" + sentence]
            result = subprocess.run(command, cwd=TREE, env=env, capture_output=True, text=True, check=False)
            try:
                actual = json.loads(result.stdout)
            except json.JSONDecodeError:
                actual = {"unparsed_stdout": result.stdout}
            rows.append({"id": f"{lang.upper()}{i:03d}", "lang": lang, "text": sentence,
                         "command": command, "returncode": result.returncode, "actual": actual,
                         "stderr": result.stderr})
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"Japanese": len(JA), "English": len(EN), "total": len(rows), "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
