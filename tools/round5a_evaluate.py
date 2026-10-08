#!/usr/bin/env python3
"""All80 immutable public one.Vera runs. No fixture writes or sealed inputs."""
import argparse
from collections import Counter,defaultdict
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import time
import traceback
from round5a_support import ROOT, environment, hashes, memory_bytes, write
from verantyx.one import Vera

APPROVED='a765402a5fc88176dd17833730780c3b8c917f7c3d80a7748277c61845c1c693'

def latency(values):
    if not values:return None
    v=sorted(values);return {'median_ms':statistics.median(v),'p95_ms':v[math.ceil(.95*len(v))-1],'max_ms':max(v)}

def normal(value):
    value=re.sub(r'\s+','',str(value)).strip('。！？?')
    m=re.fullmatch(r'([+-]?[0-9]+(?:\.[0-9]+)?)([^0-9\s]+)',value)
    return (Decimal(m[1]),m[2]) if m else value

def verdict(value):
    return 'UNKNOWN' if value.startswith('UNKNOWN') else value

def score(row,result):
    e=row['expected'];v=verdict(result.get('verdict','UNKNOWN_ERROR'));actual=result.get('values',[])
    values_match=[normal(s) for s in actual]==[normal(s) for s in e['values']]
    out=result.get('answer_values',[])
    boolean=bool(out) and all(isinstance(v,bool) for _,v in out)
    boolean_question=(not re.search(r'誰|だれ|何|なに|どこ|いつ|どの|どれ|どちら|いくつ|いくら',row['question'])
                      and not re.search(r'は[？?。]*$',row['question']))
    ep=e.get('polarity');ap=result.get('polarity')
    polarity_match=ep is None or (ap is not None and (ap=='+' if ep else ap=='-'))
    if boolean and boolean_question and ep is not None:
        values_match=len(out)==1 and out[0][1] is ep
    cited={s['source'] for s in result.get('sources',[])}
    source_match=set(e['source_ids'])<=cited
    good=(e['verdict']=='ANSWER' and v=='ANSWER' and values_match and polarity_match and source_match)
    category='correct' if good else 'wrong' if v=='ANSWER' else 'abstain'
    return {'category':category,'values_match':values_match,'polarity_match':polarity_match,'source_match':source_match,
            'verdict_match':v==e['verdict'],'appropriate_refusal':v!='ANSWER' and v==e['verdict'],
            'reference':e,'cited_source_ids':sorted(cited),'semantic_verified':result.get('semantic',{}).get('verified',False)}

def run_case(row):
    started=time.perf_counter();v=Vera.from_texts({d['id']:d['text'] for d in row['documents']},mode='semantic')
    init=(time.perf_counter()-started)*1000
    started=time.perf_counter()
    try:answer=v.ask(row['question'])
    except Exception as exc:
        answer={'kind':'unknown','verdict':'UNKNOWN_RUNTIME_ERROR','values':[],'text':'','sources':[],
                'exception':repr(exc),'traceback':traceback.format_exc()}
    ask=(time.perf_counter()-started)*1000;v.close()
    return {'id':row['id'],'family':row['family'],'question':row['question'],'documents':row['documents'],
            'initialization_ms':init,'ask_ms':ask,'answer':answer,'score':score(row,answer),
            'pair_id':row.get('pair_id'),'relation':row.get('relation')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixtures',type=Path,required=True);parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--gates',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if sys.version_info[:2]!=(3,11):raise SystemExit('Measurement requires Python3.11')
    if any(re.search('sealed|heldout',str(p),re.I) for p in (args.fixtures,args.manifest,args.output,args.gates)):
        raise SystemExit('Only public development paths are allowed')
    gate=json.loads((args.gates/'gates.json').read_text())
    if not gate['passed'] or not gate['source_unchanged'] or gate['runtime_hashes_after']!=hashes():
        raise SystemExit('Matching kernel/reader/public/adapter/compatibility gates required first')
    manifest=json.loads(args.manifest.read_text());actual_hash=hashlib.sha256(args.fixtures.read_bytes()).hexdigest()
    if (manifest.get('validation_status')!='APPROVED' or not manifest.get('ready_for_evaluation') or
        actual_hash!=APPROVED or manifest['sha256_fixtures_jsonl']!=actual_hash):raise SystemExit('Approved fixed public80 hash required')
    rows=[json.loads(s) for s in args.fixtures.read_text().splitlines() if s.strip()]
    errors=[]
    if len(rows)!=80 or len({r['id'] for r in rows})!=80:errors.append('80 unique rows required')
    for row in rows:
        if not set(row['expected']['source_ids'])<={d['id'] for d in row['documents']}:errors.append(row['id']+': missing reference source')
    if errors:
        write(args.output.parent/(args.output.name+'-fixture_inconsistencies.json'),errors)
        raise SystemExit('Fixture inconsistency recorded before runtime: '+str(errors))
    args.output.mkdir(parents=True,exist_ok=False);write(args.output/'environment.json',environment());write(args.output/'manifest.json',manifest)
    before=hashes();results=[]
    with (args.output/'answers.jsonl').open('x') as stream:
        for row in rows:
            r=run_case(row);results.append(r);stream.write(json.dumps(r,ensure_ascii=False)+'\n');stream.flush()
    families={};totals=Counter(r['score']['category'] for r in results)
    for family in sorted({r['family'] for r in results}):families[family]=dict(Counter(r['score']['category'] for r in results if r['family']==family))
    pair=defaultdict(list)
    for r in results:
        if r['pair_id']:pair[r['pair_id']].append(r)
    invariance=[]
    # Reorder document containers only, preserving every original source string.
    for row,original in zip(rows,results):
        permuted={**row,'documents':list(reversed(row['documents']))};other=run_case(permuted)
        same=(verdict(original['answer'].get('verdict',''))==verdict(other['answer'].get('verdict','')) and
              original['answer'].get('values',[])==other['answer'].get('values',[]))
        invariance.append({'id':row['id'],'same':same,'original_verdict':original['answer']['verdict'],
                           'permuted_verdict':other['answer']['verdict'],'permuted_answer':other['answer']})
    write(args.output/'document_order.json',invariance)
    payload={'count':80,'fixture_sha256':actual_hash,'primary':dict(totals),'answer_correct_rate':totals['correct']/80,
             'appropriate_refusals':sum(r['score']['appropriate_refusal'] for r in results),
             'families':families,'verdicts':dict(Counter(r['answer']['verdict'] for r in results)),
             'latency':{'initialization':latency([r['initialization_ms'] for r in results]),'ask':latency([r['ask_ms'] for r in results])},
             'peak_rss_bytes':memory_bytes(),'runtime_errors':[r['id'] for r in results if r['answer']['verdict']=='UNKNOWN_RUNTIME_ERROR'],
             'budget_refusals':sum(r['answer']['verdict']=='UNKNOWN_BUDGET' for r in results),
             'order_changes':sum(not r['same'] for r in invariance),
             'pairs':{key:{'relation':rows_[0]['relation'],'ids':[r['id'] for r in rows_],
                           'both_correct_answers':all(r['score']['category']=='correct' for r in rows_),
                           'verdict_and_values':[(r['answer']['verdict'],r['answer'].get('values',[])) for r in rows_]} for key,rows_ in pair.items()},
             'injection_cases':[{key:r[key] for key in ('id','answer','score')} for r in results if r['family']=='injection'],
             'runtime_hashes_before':before,'runtime_hashes_after':hashes(),'source_unchanged':before==hashes(),
             'adoption':False,'new_sealed_evaluation':False,'limitations':'Development results only. No generalization proof. B/C unimplemented.'}
    write(args.output/'summary.json',payload)
    print(json.dumps({k:payload[k] for k in ('primary','appropriate_refusals','latency','runtime_errors','order_changes')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
