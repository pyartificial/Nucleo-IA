#!/usr/bin/env python3
import csv,glob,os,json
root=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
files=sorted(glob.glob(os.path.join(root,'state','health-*.csv')))
if not files:
    print('no health files'); raise SystemExit(1)
latest=files[-1]
rows=list(csv.DictReader(open(latest)))
ok=sum(1 for r in rows if r['status']=='OK')
total=len(rows)
score=round((ok/total)*100,2) if total else 0
out={"latest":os.path.basename(latest),"ok":ok,"total":total,"score":score}
open(os.path.join(root,'state','priority.json'),'w').write(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))