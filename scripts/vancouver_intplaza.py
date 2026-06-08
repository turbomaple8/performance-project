import gspread
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly',
          'https://www.googleapis.com/auth/drive.readonly']
creds = Credentials.from_service_account_file('config/service-account.json', scopes=SCOPES)
gc = gspread.authorize(creds)
sh = gc.open_by_key('1qMcSju_Pa6yq_h1yazNXvj_l1WUO9I5qhaWBFNrpn_o')
ws = sh.worksheet('Int Plaza')
vals = ws.get('A4:K54')

F = 4.34524  # weeks per month (52.143/12)


def num(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == '':
        return None
    s = s.replace('CA$', '').replace('$', '').replace(',', '').replace('CA', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


mr_total = 0.0
amt_total = 0.0
vac_total = 0.0
vac_rooms = []
occ_count = 0
rooms = 0
no_amount = []

for r in vals:
    r = list(r) + [''] * (11 - len(r))
    no, apt, rtype = r[0], r[1], r[2]
    mr, amt = num(r[3]), num(r[4])
    plan, avail = str(r[5]).strip(), str(r[9]).strip().lower()
    if no is None or str(no).strip() == '':
        continue
    rooms += 1
    if mr is not None:
        mr_total += mr * F
    if avail == 'vacant':
        vm = mr * F if mr is not None else 0
        vac_total += vm
        vac_rooms.append((no, apt, rtype, mr, round(vm, 2)))
    if avail == 'occupied':
        occ_count += 1
        if amt is not None and amt > 0:
            m = amt * F if plan.lower().startswith('four') else amt
            amt_total += m
        else:
            no_amount.append((no, apt, rtype, plan))

print('Rooms: %d | Occupied: %d | Vacant: %d' % (rooms, occ_count, len(vac_rooms)))
print()
print('=== 1) MARKET RENT TOTAL (monthly) ===')
print('  factor 4.34524 : CA$ {:,.2f}'.format(mr_total))
print('  factor 52/12   : CA$ {:,.2f}'.format(mr_total / F * (52 / 12)))
print()
print('=== 2) VACANCY ===')
for v in vac_rooms:
    print('  No.{} Apt {} {} | MR {}/wk -> {:,}/mo'.format(*v))
print('  Vacant count: %d' % len(vac_rooms))
print('  Total vacant market rent (monthly): CA$ {:,.2f}'.format(vac_total))
print()
print('=== 3) AMOUNT COLLECTED (occupied only, monthly) ===')
print('  Total: CA$ {:,.2f}'.format(amt_total))
print()
print('  Occupied rooms with NO amount entered:')
for s in no_amount:
    print('   No.{} Apt {} {} ({})'.format(*s))
