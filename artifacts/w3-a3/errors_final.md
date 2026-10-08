# W3-a3: verbs of verb_check_300.jsonl on r6/run1
(run 001, content_sha256 5c969d454b39d39ac0e394191b5e985b4e0a10099591bb7b12fcc559e7d77ff1)

## direct answers that are wrong (typed words)
- 冠する gold=P_ACT,P_GIVE top=P_COMMUNICATE by=gen_frame+role_distribution@jawiki

## direct answers that are right
- 頼める gold=P_COMMUNICATE,P_STATE top=P_COMMUNICATE by=gen_frame+role_distribution@codex:general_qa+role_distribution@codex:paraphrase_entail frame_status=CONFIRMED
- 口ずさむ gold=P_COMMUNICATE top=P_COMMUNICATE by=gen_frame+role_distribution@codex:figurative_commonsense+role_distribution@codex:narrative+role_distribution@codex:pro frame_status=CONFIRMED
- 読み上げる gold=P_COMMUNICATE,P_PERCEIVE top=P_COMMUNICATE by=gen_frame+role_distribution@codex:narrative+role_distribution@codex:paraphrase_entail+role_distribution@jawiki frame_status=CONFIRMED
- 論ずる gold=P_COMMUNICATE top=P_COMMUNICATE by=gen_frame+role_distribution@jawiki frame_status=CONFIRMED

## words that are not typed but got a type (any origin)
- ジョヴァぽむ kind=unknown_coined top=PERSON origin=estimated basis=proximity by=est:morphology:head

## estimated (generated) typed answers: right / wrong counts
- right 192, wrong 56, other 0
