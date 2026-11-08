#!/usr/bin/env python3
"""Fetch explicitly ordered NBA conference tables; never guess ordering from API arrays.

Source: Iskoran published ranking (third-party, tie breaking by point differential).
Optional second-source W/L corroboration: StandingsToday. Fail closed on stale,
partial, inconsistent, malformed, or regressing records. Do not label as official.
"""
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data.json'
SEASON = '2026-27'
PRIMARY = 'https://iskoran.com/nba/standings/'
SECONDARY = 'https://standingstoday.com/nba/'
E = set('TOR MIA NYK PHI BOS CLE DET ORL IND WAS ATL CHI CHA MIL BKN'.split())
W = set('OKC SAS HOU DEN LAL UTA MIN PHX DAL POR GSW MEM LAC NOP SAC'.split())
NAMES = {
 'ATL':'Atlanta Hawks','BOS':'Boston Celtics','BKN':'Brooklyn Nets','CHA':'Charlotte Hornets',
 'CHI':'Chicago Bulls','CLE':'Cleveland Cavaliers','DAL':'Dallas Mavericks','DEN':'Denver Nuggets',
 'DET':'Detroit Pistons','GSW':'Golden State Warriors','HOU':'Houston Rockets','IND':'Indiana Pacers',
 'LAC':'LA Clippers','LAL':'Los Angeles Lakers','MEM':'Memphis Grizzlies','MIA':'Miami Heat',
 'MIL':'Milwaukee Bucks','MIN':'Minnesota Timberwolves','NOP':'New Orleans Pelicans',
 'NYK':'New York Knicks','OKC':'Oklahoma City Thunder','ORL':'Orlando Magic','PHI':'Philadelphia 76ers',
 'PHX':'Phoenix Suns','POR':'Portland Trail Blazers','SAC':'Sacramento Kings','SAS':'San Antonio Spurs',
 'TOR':'Toronto Raptors','UTA':'Utah Jazz','WAS':'Washington Wizards'
}
ALIAS = {'LAC':['Los Angeles Clippers'], 'POR':['Portland TrailBlazers','Portland Trailblazers'],
         'SAS':['San Antonio Spurs'], 'NYK':['New York Knicks']}


def request_text(url):
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0 (compatible; NBA-Prediction-Standings/2.0; +https://github.com/)',
        'Accept':'text/html,application/xhtml+xml', 'Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=18) as response:
        if response.status != 200: raise ValueError(f'{url}: HTTP {response.status}')
        return response.read(3_000_000).decode('utf-8',errors='replace')


def identify_team(name):
    s=re.sub(r'[^a-z0-9]+',' ',name.casefold()).strip()
    for code,full in NAMES.items():
        for alias in [full]+ALIAS.get(code,[]):
            a=re.sub(r'[^a-z0-9]+',' ',alias.casefold()).strip()
            if a and (s==a or s.startswith(a+' ') or s.endswith(' '+a)):
                return code
    return None


def source_date(soup):
    # The publisher uses a human-readable update stamp. Never substitute scrape time.
    text=soup.get_text(' ',strip=True)
    m=re.search(r'Updated\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d\d)',text,re.I)
    if not m: raise ValueError('Primary standings missing explicit Updated date')
    return dt.datetime.strptime(' '.join(m.groups()),'%B %d %Y').date()


def parse_iskoran(html):
    soup=BeautifulSoup(html,'html.parser')
    if '2026-27' not in soup.get_text(' ',strip=True):
        raise ValueError('Primary page does not identify 2026-27 NBA season')
    published=source_date(soup)
    ranks={}; records={}
    for label,allowed in [('East',E),('West',W)]:
        heading=next((h for h in soup.find_all(['h1','h2','h3']) if h.get_text(' ',strip=True).lower()==label.lower()),None)
        if heading is None: raise ValueError(f'Missing {label} conference heading')
        table=heading.find_next('table')
        if table is None: raise ValueError(f'Missing {label} standings table')
        entries=[]
        for tr in table.find_all('tr'):
            tds=tr.find_all('td')
            if len(tds)<4: continue
            rank_str=tds[0].get_text(' ',strip=True)
            if not rank_str.isdigit(): continue
            rank=int(rank_str)
            code=identify_team(tds[1].get_text(' ',strip=True))
            if code is None: raise ValueError('Unknown NBA team: '+tds[1].get_text(' ',strip=True))
            if code not in allowed: raise ValueError(f'{code} in wrong conference')
            w=int(tds[2].get_text(' ',strip=True)); l=int(tds[3].get_text(' ',strip=True))
            if min(w,l)<0 or w+l>82: raise ValueError(f'Invalid {code} season record')
            entries.append((rank,code)); records[code]={'wins':w,'losses':l}
        if len(entries)!=15 or {r for r,_ in entries}!=set(range(1,16)) or {c for _,c in entries}!=allowed:
            raise ValueError(f'Invalid {label} ranks: expected 15 unique complete ranks; got {entries}')
        ranks[label[0].upper()]=[code for _,code in sorted(entries)]
    return published,ranks,records


def parse_secondary_records(html):
    """Independent W/L corroboration; its page is organized by divisions, not overall rank."""
    soup=BeautifulSoup(html,'html.parser')
    if '2026-27' not in soup.get_text(' ',strip=True):
        raise ValueError('Secondary standings have wrong season')
    found={}
    for tr in soup.find_all('tr'):
        tds=tr.find_all('td')
        if len(tds)<4 or not tds[0].get_text(' ',strip=True).isdigit():continue
        code=identify_team(tds[1].get_text(' ',strip=True))
        if not code: continue
        a=tds[2].get_text(' ',strip=True);b=tds[3].get_text(' ',strip=True)
        if not (a.isdigit() and b.isdigit()):continue
        record={'wins':int(a),'losses':int(b)}
        if code in found and found[code]!=record:raise ValueError(f'Secondary has inconsistent {code} records')
        found[code]=record
    if set(found)!=set(NAMES):raise ValueError(f'Secondary incomplete ({len(found)}/30 teams)')
    return found


def validate_freshness(published,now):
    age=(now.date()-published).days
    if not 0<=age<=1:
        raise ValueError(f'Source outdated or future dated: published={published}, today={now.date()}')


def validate_previous(snapshots,records,today):
    for prior in reversed(sorted(snapshots,key=lambda s:s.get('date',''))):
        if prior.get('date','')>today or not prior.get('records'):continue
        if prior.get('verification') not in ('third-party-crosschecked','third-party'):continue
        for code,record in records.items():
            old=prior['records'].get(code)
            if old and (record['wins']<old['wins'] or record['losses']<old['losses']):
                raise ValueError(f'{code} W/L went backwards; refuse stale snapshot')
        break


def main():
    now=dt.datetime.now(ZoneInfo('Asia/Taipei'))
    published,ranks,records=parse_iskoran(request_text(PRIMARY))
    validate_freshness(published,now)
    check='not-available'
    try:
        alternate=parse_secondary_records(request_text(SECONDARY))
        disagreements={code:(records[code],alternate[code]) for code in NAMES if records[code]!=alternate[code]}
        if disagreements:raise ValueError(f'Independent source W/L mismatches: {disagreements}')
        check='matched-30-records'
    except (OSError,TimeoutError,ValueError) as ex:
        # A mismatch is a hard error; missing secondary feed is an explicit caveat.
        if 'mismatches' in str(ex):raise
        print('Secondary cross-check unavailable:',str(ex))
    today=now.date().isoformat()
    stored=json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'season':SEASON,'snapshots':[]}
    if stored.get('season')!=SEASON:raise ValueError('Season mismatch in existing data file')
    snaps=stored.get('snapshots',[])
    validate_previous(snaps,records,today)
    stamp=now.isoformat(timespec='seconds')
    snap={'date':today,'E':ranks['E'],'W':ranks['W'],'source':'Iskoran (third-party)',
          'verification':'third-party-crosschecked' if check=='matched-30-records' else 'third-party',
          'crossCheck':check,'tieBreaker':'Win percentage, then wins and point differential (publisher policy; not NBA official)',
          'sourceDate':published.isoformat(),'sourceUrl':PRIMARY,'retrievedAt':stamp,'records':records}
    # Preserve earlier entries, but never mislabel legacy ESPN results as official.
    for previous in snaps:
        if previous.get('source','').startswith('ESPN') and previous.get('verification') not in ('official',):
            previous['verification']='unverified'
    snaps=[s for s in snaps if s.get('date')!=today]+[snap]
    stored.update({'season':SEASON,'sourceUrl':PRIMARY,'lastUpdated':stamp,
                   'snapshots':sorted(snaps,key=lambda s:s['date'])})
    stored.pop('apiUrl',None)
    tmp=OUT.with_name('data.json.tmp')
    tmp.write_text(json.dumps(stored,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(tmp,OUT)
    print(f'SUCCESS: {today}, source date {published}, corroboration={check}')
    print('EAST:',','.join(ranks['E']))
    print('WEST:',','.join(ranks['W']))

if __name__=='__main__':main()
