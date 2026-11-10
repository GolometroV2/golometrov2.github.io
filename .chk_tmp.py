import json
d=json.load(open('mister_fantasy_data.json'))
print(list(d.keys()))
md=d['matchdays']
print(d['managers'][0].keys())
for m in d['managers']:
    t=0;b=0
    for j,jj in md.items():
        x=jj.get(m['id'])
        if not x: continue
        t+=x['points']; c=x.get('captain')
        if c and c.get('basePoints') is not None: b+=c['basePoints']*(c.get('multiplier',2)-1)
    print(m['name'],m.get('points'),t,b)
