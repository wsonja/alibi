import json, re, sys
case = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'backend/app/cases/vane_hall.json'))
errs = []
sus = {s['id']: s for s in case['suspects']}
ev  = {e['id'] for e in case['evidence']} | {e['id'] for e in case.get('dynamic_evidence', [])}
loc = {l['id'] for l in case['locations']}
sec = {s['id']: sid for sid in sus for s in sus[sid]['secrets']}
tactics = {'evidence','threaten','flatter','bluff','silence'}

TOKEN = re.compile(r'^(evidence:\w+|known:\w+|revealed:\w+|stress>=\d+|flatter_count>=\d+|threaten_count>=\d+|turn>=\d+|searched:\w+|clock>=\d\d:\d\d)$')
def check_cond(expr, ctx):
    for part in re.split(r'\s+(?:and|or)\s+', expr):
        tok = part[4:] if part.startswith('not ') else part
        if not TOKEN.match(tok): errs.append(f'{ctx}: bad token {tok!r}')
        kind, _, val = tok.partition(':')
        if kind == 'evidence' or kind == 'known':
            if val not in ev: errs.append(f'{ctx}: unknown evidence {val}')
        elif kind == 'revealed':
            if val not in sec: errs.append(f'{ctx}: unknown secret {val}')
        elif kind == 'searched':
            if val not in loc: errs.append(f'{ctx}: unknown location {val}')

# locations <-> evidence
for l in case['locations']:
    for eid in l['evidence_ids']:
        if eid not in ev: errs.append(f'location {l["id"]}: unknown evidence {eid}')
for e in case['evidence'] + case.get('dynamic_evidence', []):
    if e['location'] not in loc: errs.append(f'evidence {e["id"]}: unknown location')
    for k in ('id','name','location','initially_known','description','examined_detail','points_to'):
        if k not in e: errs.append(f'evidence {e["id"]}: missing {k}')
listed = {eid for l in case['locations'] for eid in l['evidence_ids']}
for e in case['evidence']:
    if e['id'] not in listed: errs.append(f'evidence {e["id"]} not listed under any location')

# suspects
guilty = [s for s in sus.values() if s['guilty']]
if len(guilty) != 1: errs.append(f'expected exactly one guilty, got {len(guilty)}')
req = ['id','name','role','public_description','persona','speech_quirk','portrait_prompt','personality','goals','knowledge','secrets','stress_sensitivity','crack_thresholds','special_unlocks','shutdown_rules','deflections','framing_actions','tells','guilty','relationships']
for sid, s in sus.items():
    for k in req:
        if k not in s: errs.append(f'{sid}: missing {k}')
    if set(s['stress_sensitivity']) != tactics: errs.append(f'{sid}: sensitivity keys {set(s["stress_sensitivity"])}')
    if len(s['crack_thresholds']) != 3 or s['crack_thresholds'] != sorted(s['crack_thresholds']): errs.append(f'{sid}: thresholds')
    tiers = sorted(x['tier'] for x in s['secrets'])
    if tiers != [1,2,3]: errs.append(f'{sid}: secret tiers {tiers}')
    for x in s['secrets']:
        if 'key_phrases' not in x: errs.append(f'{sid}/{x["id"]}: no key_phrases')
        else: re.compile(x['key_phrases'])
    for secid, rule in s['special_unlocks'].items():
        if sec.get(secid) != sid: errs.append(f'{sid}: special_unlocks for foreign/unknown secret {secid}')
        for c in rule.get('requires_any', []) + rule.get('requires_all', []): check_cond(c, f'{sid}/{secid}')
        for r in rule.get('requires_revealed', []):
            if r not in sec: errs.append(f'{sid}/{secid}: requires_revealed unknown {r}')
    for t in s['shutdown_rules']:
        if t not in tactics: errs.append(f'{sid}: shutdown tactic {t}')
    for fa in s['framing_actions']:
        check_cond(fa['trigger'], f'{sid}/{fa["id"]}')
        eff = fa['effect']
        if 'remove_evidence' in eff and eff['remove_evidence'] not in ev: errs.append(f'{sid}/{fa["id"]}: remove unknown')
        if 'add_evidence_id' in eff and eff['add_evidence_id'] not in {e['id'] for e in case['dynamic_evidence']}: errs.append(f'{sid}/{fa["id"]}: add not dynamic')
    for other, rel in s['relationships'].items():
        if other not in sus or other == sid: errs.append(f'{sid}: relationship {other}')
        if not 0 <= rel['trust'] <= 1: errs.append(f'{sid}: trust {other}')
    if set(s['relationships']) != set(sus) - {sid}: errs.append(f'{sid}: relationships incomplete')
    if set(s['tells']) != {'nervous','angry','cracking'}: errs.append(f'{sid}: tells')
    if not s['deflections']: errs.append(f'{sid}: no deflections')
    if s['guilty']:
        conf = [x for x in s['secrets'] if x.get('is_confession')]
        if len(conf) != 1 or conf[0]['tier'] != 3: errs.append(f'{sid}: confession secret')
        rule = s['special_unlocks'].get(conf[0]['id'], {}) if conf else {}
        if not any(c.startswith('evidence:') for c in rule.get('requires_any', []) + rule.get('requires_all', [])):
            errs.append(f'{sid}: confession must require physical evidence')

# solution
sol = case['solution']
if sol['murderer'] not in sus or not sus[sol['murderer']]['guilty']: errs.append('solution.murderer mismatch')
for k in ('method_evidence_ids','motive_evidence_ids'):
    for eid in sol[k]:
        if eid not in ev: errs.append(f'solution.{k}: unknown {eid}')
if len(sol['proof_paths']) < 2: errs.append('need >=2 proof paths')
for i, path in enumerate(sol['proof_paths']):
    for tok in path: check_cond(tok, f'proof_path[{i}]')

# proof-path satisfiability: simulate unlocking with unlimited stress but honoring special_unlocks
def satisfiable(path):
    examined, revealed = set(), set()
    def holds(c):
        neg = c.startswith('not ')
        c = c[4:] if neg else c
        k,_,v = c.partition(':')
        if k=='evidence': r = v in examined
        elif k=='revealed': r = v in revealed
        elif c.startswith('stress>=') or c.startswith('flatter_count>=') or c.startswith('turn>='): r = True
        else: r = False
        return (not r) if neg else r
    for tok in path:
        k,_,v = tok.partition(':')
        if k == 'evidence': examined.add(v); continue
        owner = sus[sec[v]]
        rule = owner['special_unlocks'].get(v, {})
        ok = (not rule.get('requires_any') or any(holds(c) for c in rule['requires_any'])) \
             and all(holds(c) for c in rule.get('requires_all', [])) \
             and all(r in revealed for r in rule.get('requires_revealed', []))
        if not ok: return f'{tok} not unlockable at that point'
        revealed.add(v)
    return None
for i, path in enumerate(sol['proof_paths']):
    r = satisfiable(path)
    if r: errs.append(f'proof_path[{i}]: {r}')

for rs in case['rumor_seeds']:
    if rs['holder'] not in sus: errs.append('rumor holder')
    for t in rs['spreads_to']:
        if t not in sus: errs.append('rumor target')

print('suspects:', list(sus)); print('evidence:', sorted(ev)); print('secrets:', list(sec))
print('ERRORS:' if errs else 'OK — no errors'); [print(' -', e) for e in errs]
sys.exit(1 if errs else 0)
