# keep the old hand classification only for rows that are still new-vs-dev in the current table (a row for a reading that is gone no longer applies)
import csv, sys
A='/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S/artifacts/w1-a/'
old=open(A+'x3_classified.tsv',encoding='utf-8').read().splitlines()
table=[r for r in csv.reader(open(A+'x3_table.tsv',encoding='utf-8'),delimiter='\t')][1:]
keys={(r[0],r[1],r[2]) for r in table}
keep=[l for l in old if l.startswith('#') or tuple(l.split('\t')[:3]) in keys]
dropped=[l for l in old if l not in keep]
open(A+'x3_classified.tsv','w',encoding='utf-8').write('\n'.join(keep)+'\n')
print('kept',len(keep),'dropped',len(dropped))
for l in dropped[:40]: print('  dropped:',l[:120])
