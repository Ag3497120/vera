# PUB-M5/M6 — 書き込みの時間（L-PUB-40）

1000 文（5 セッション、受理 960）。100 書き込みごとの 1 書き込みあたりの秒:

| 書き込み済み | 受理済み | 秒/書き込み |
|---|---|---|
| 100 | 96 | 0.0515 |
| 200 | 192 | 0.1056 |
| 300 | 288 | 0.1722 |
| 400 | 384 | 0.2259 |
| 500 | 480 | 0.3075 |
| 600 | 576 | 0.4053 |
| 700 | 672 | 0.538 |
| 800 | 768 | 0.6434 |
| 900 | 864 | 0.7759 |
| 1000 | 960 | 0.9248 |

recall の秒（250 書き込みごと）: [0.1406, 0.0552, 0.0942, 0.5263]

増分の索引 = 作り直し: {'sentences': 288, 'same_json': True, 'same_sha': True, 'sha': '6f924da9a29338893888241ad243f87826d5d5b6bcea7d87c1a5deedf14006d6', 'assemble_equals_canonical': True}

最後の 20 書き込みの cProfile（累積）:

```
         28293361 function calls (28218637 primitive calls) in 25.298 seconds

   Ordered by: cumulative time
   List reduced from 659 to 25 due to restriction <25>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
       21    0.001    0.000   25.783    1.228 /home/runner/work/vera/vera/verantyx/loom/memory.py:1422(call)
       40    0.000    0.000   24.061    0.602 /home/runner/work/vera/vera/verantyx/loom/ops.py:320(step)
       21    0.001    0.000   17.784    0.847 /home/runner/work/vera/vera/verantyx/loom/memory.py:482(_model_step)
       40    0.250    0.006   12.794    0.320 /home/runner/work/vera/vera/verantyx/loom/memory.py:427(mem_state_sha)
       20    0.049    0.002   11.259    0.563 /home/runner/work/vera/vera/verantyx/loom/memory.py:563(h_write)
       20    0.005    0.000   11.210    0.561 /home/runner/work/vera/vera/verantyx/loom/memory.py:677(_write_v4)
       40    0.002    0.000    7.329    0.183 /home/runner/work/vera/vera/verantyx/loom/state.py:322(to_obj)
       40    0.094    0.002    6.288    0.157 /home/runner/work/vera/vera/verantyx/loom/state.py:324(<dictcomp>)
       19    0.000    0.000    6.276    0.330 /home/runner/work/vera/vera/verantyx/loom/memory.py:525(_outside_step)
   233660    0.207    0.000    6.195    0.000 /home/runner/work/vera/vera/verantyx/loom/state.py:225(to_obj)
   233660    5.988    0.000    5.988    0.000 /home/runner/work/vera/vera/verantyx/loom/state.py:227(<listcomp>)
       19    0.000    0.000    5.489    0.289 /home/runner/work/vera/vera/verantyx/loom/memory.py:233(build_corpus)
       19    0.023    0.001    5.322    0.280 /home/runner/work/vera/vera/verantyx/loom/corpus.py:30(__init__)
    74970    0.067    0.000    5.249    0.000 /opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/json/__init__.py:183(dumps)
    74970    0.058    0.000    5.158    0.000 /opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/json/encoder.py:183(encode)
    74659    0.027    0.000    5.128    0.000 /home/runner/work/vera/vera/verantyx/loom/state.py:85(canonical)
    74780    5.015    0.000    5.015    0.000 /opt/hostedtoolcache/Python/3.11.14/x64/lib/python3.11/json/encoder.py:205(iterencode)
       19    0.001    0.000    4.459    0.235 /home/runner/work/vera/vera/verantyx/loom/memnotes.py:372(compute_write_notes)
       19    0.001    0.000    3.274    0.172 /home/runner/work/vera/vera/verantyx/line3/foundation.py:392(adhesions_of_space)
       22    0.114    0.005    3.232    0.147 /home/runner/work/vera/vera/verantyx/loom/memrecall.py:128(judge_memory)
    65702    0.617    0.000    2.984    0.000 /home/runner/work/vera/vera/verantyx/loom/evidence.py:505(judge_quote)
       19    0.000    0.000    2.835    0.149 /home/runner/work/vera/vera/verantyx/loom/memrecall.py:265(__call__)
       19    0.000    0.000    2.298    0.121 /home/runner/work/vera/vera/verantyx/line3/grammar.py:284(records_of_space)
       19    0.291    0.015    2.293    0.121 /home/runner/work/vera/vera/verantyx/line3/grammar.py:290(_build)
       40    0.002    0.000    1.719    0.043 /home/runner/work/vera/vera/verantyx/loom/ledger.py:131(append)



```
