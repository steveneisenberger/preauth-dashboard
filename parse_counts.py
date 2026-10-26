# Pre-auth PDF parser (Dashy's original logic, adapted for Benny-PC)
# Usage: python parse_counts.py <preauth.pdf> <out.json>
# Writes COUNTS ONLY: [{office, insurer, status, count}, ...]. Prints summary only, never patient rows.
import pdfplumber, collections, re, datetime, json, sys

pdf_path, out_path = sys.argv[1], sys.argv[2]
today = datetime.date.today()
try:
    cutoff = today.replace(year=today.year - 2)
except ValueError:                       # Feb 29
    cutoff = today.replace(year=today.year - 2, day=28)

OFF = {'HAN': 'HP', 'BP': 'BP', 'WAL': 'WAL'}
ST = {'MC': 'MC', 'SUB': 'SUB', 'APP-MC': 'APP-MC', 'REJ-MC': 'REJ-MC',
      '(1) MC PH1': 'MC PH1', '(1) PH1SUB': 'PH1 SUB', '(1)PH1 APP': 'PH1 APP'}
STATUSES = ['MC', 'SUB', 'APP-MC', 'REJ-MC', 'MC PH1', 'PH1 SUB', 'PH1 APP']
GROUPS = [('HP', 'DentaQuest'), ('HP', 'United Healthcare'), ('BP', 'DentaQuest'), ('BP', 'United Healthcare'),
          ('WAL', 'DentaQuest'), ('WAL', 'United Healthcare'), ('WAL', 'Liberty Dental')]

def ins(h):
    u = h.upper().replace(' ', '')
    if u.startswith('DQ') or 'DENTAQUEST' in u: return 'DentaQuest'
    if u.startswith('UNITEDHEALTH'): return 'United Healthcare'
    if u.startswith('LIBERTY'): return 'Liberty Dental'
    return None

cnt = collections.Counter(); old = nodate = other = liberty_hp_bp = pages_read = 0
with pdfplumber.open(pdf_path) as pdf:
    for p in pdf.pages:
        ws = p.extract_words()
        idh = [w for w in ws if w['text'] == 'ID']; hx = [w for w in ws if w['text'] == 'HMO']; ox = [w for w in ws if w['text'] == 'Office']
        if not (idh and hx and ox): continue
        pages_read += 1
        idh = idh[0]; hx = hx[0]; ox = ox[0]
        stw = sorted([w for w in ws if w['text'] == 'Status'], key=lambda w: abs(w['top'] - idh['top']))
        sx = stw[0]; cx = [w for w in stw[1:] if w['x0'] > sx['x0']][0]
        top = max(hx['bottom'], idh['bottom']) + 10
        anchors = sorted([w for w in ws if w['top'] > top - 8 and abs(w['x0'] - idh['x0']) < 4 and w['text'] != 'ID'], key=lambda w: w['top'])
        for i, a in enumerate(anchors):
            nxt = anchors[i + 1]['top'] if i + 1 < len(anchors) else 1e9
            col = lambda x0, x1: ' '.join(w['text'] for w in sorted([w for w in ws if a['top'] - 2 <= w['top'] < nxt - 1 and x0 - 3 <= w['x0'] < x1], key=lambda w: (w['top'], w['x0'])))
            st = ST.get(col(sx['x0'], sx['x0'] + 38)); of = OFF.get(col(ox['x0'], ox['x0'] + 35)); hm = ins(col(hx['x0'], hx['x0'] + 80))
            if not (st and of and hm): other += 1; continue
            m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', col(cx['x0'] - 5, cx['x0'] + 45))
            if not m: nodate += 1; continue
            d = datetime.date(int(m[3]), int(m[1]), int(m[2]))
            if d < cutoff: old += 1; continue
            if hm == 'Liberty Dental' and of != 'WAL': liberty_hp_bp += 1; continue   # site shows Liberty for WAL only
            cnt[(of, hm, st)] += 1

kept = sum(cnt.values())
print(f"pages {pages_read} | cutoff {cutoff} | kept {kept} | older {old} | no date {nodate} | other office/ins/status {other} | Liberty at HP/BP skipped {liberty_hp_bp}")
if pages_read == 0 or kept == 0:
    print("ERROR: nothing counted; export looks wrong. Not saving.")
    sys.exit(1)

rows = [{'office': o, 'insurer': i, 'status': s, 'count': cnt[(o, i, s)]} for o, i in GROUPS for s in STATUSES]
with open(out_path, 'w', encoding='utf-8') as fh:
    json.dump(rows, fh, separators=(',', ':'))
print(f"Saved {out_path}")
