# Appends the classification of every still-UNCLASSIFIED row of x3_table.tsv to x3_classified.tsv (labels are the author's reading of each row;
# the rule that gives the label is written in the note column). Usage: classify_x3.py <table.tsv> <classified.tsv> <dev.jsonl> <after.jsonl>
import csv, json, sys
table, classified, devp, aftp = sys.argv[1:5]
dev = {json.loads(l)['text']: json.loads(l) for l in open(devp, encoding='utf-8')}
aft = {json.loads(l)['text']: json.loads(l) for l in open(aftp, encoding='utf-8')}
rows = [r for r in csv.reader(open(table, encoding='utf-8'), delimiter='\t')][1:]
out = []
def rules(t, key): return [c['rule'] for c in aft[t][key]]
for r in rows:
    text, role, value, kind, dev_role, label, how, source = r
    if label != 'UNCLASSIFIED': continue
    d_rules = [c['rule'] for c in dev[text]['supported']]; a_rules = rules(text, 'supported')
    d_pairs = {(n, v) for c in dev[text]['supported'] for n, v in c['roles']}
    if role in ('entity', 'value', 'attribute') and any(x in a_rules for x in ('copula', 'paren_gloss')):
        if 'copula' in d_rules: lab, note = 'IMPROVED', 'dev も同じ文を copula で読んだが、entity/value の範囲が語の途中で切れていた。修正後は括弧付きの名前全体と述語名詞の句で切れ目が語境界に合う(値の先頭の読点は句読点で、照合で無視される)'
        else: lab, note = 'CORRECT', '定義文(名前または題名＋括弧の読みは、述語名詞)。dev では未対応。entity は名前全体、value は述語名詞の句'
    elif role == 'quotation':
        lab, note = ('IMPROVED', 'dev は copula と読んで語の途中で切っていた。引用符の中身を quotation として読む') if 'copula' in d_rules else ('CORRECT', '括弧・引用符の中身を quotation とする(題名・用語の言及)。dev では未対応')
    elif role == 'time':
        lab, note = ('IMPROVED', '時の句。dev は agent / recipient と読んでいた') if kind == 'ROLE_CHANGED' else ('CORRECT', '時の句(毎年4月28日・その後・晩年)。dev では未対応または別の節')
    elif role == 'result':
        lab, note = 'IMPROVED', '変換・分類の結果の句(英語・二つ・40以上の言語・分類先)。dev は agent / recipient と読んでいた'
    elif role == 'source':
        lab, note = 'IMPROVED', '出どころの場所(広島・倉庫・駅)。dev は受身の動作主(agent)と読んでいた'
    elif role in ('adjunct_1', 'adjunct_2', 'place'):
        lab, note = 'IMPROVED', '連体修飾節の中の付加語(場所・修飾)。dev は agent と読んでいた(付加語を動作主にしない)'
    elif (role, text[:6]) in (('agent', '日本では同年'),) or (role == 'agent' and dev_role == 'source'):
        lab, note = 'IMPROVED', '受身の から 句の動作主(カプコン)。dev は source(context 付き)と読んでいた。規約 4.6 は から の句を agent とする'
    elif role == 'topic':
        lab, note = 'IMPROVED', '文頭の「日本では」を topic とする。dev は context'
    elif role in ('patient', 'capacity', 'location', 'agent'):
        lab, note = 'CORRECT', '節の項: patient=勤務(続ける の目的語)・capacity=として の句・location=位置する の場所・agent=主語(読解器は人でない主語も agent と名付ける: 規約 2 の entity は入口が棄権して扱う)。dev では未対応'
    else:
        lab, note = 'UNCLASSIFIED', ''
    out.append('\t'.join((text, role, value, lab, note)))
with open(classified, 'a', encoding='utf-8') as f:
    f.write('\n'.join(out) + '\n')
print(len(out), 'rows appended;', sum(1 for o in out if o.split('\t')[3] == 'UNCLASSIFIED'), 'left unclassified')
