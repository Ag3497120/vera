from verantyx.coarse_place import query
P='/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1'
for t in ['3年後','5日前','21世紀末','３年後','10分後','2週間後','3か月後','10秒ごと','7日目','3日分','千日前','三年後','2年生','3分の1','10メートル','10ms','ＮＰＯ','NPO','ｱｻﾞﾐ','アザミ','あざみ']:
    r=query(t,placement=P); print(t, r['state'], r['top'], (r['axes'].get('notation') or {}).get('rule'), r['origin'])
