#!/usr/bin/env python3
"""Official NBA conference ranking only; fail closed, never infer tie-breakers.

A successful HTTP fetch is not a successful snapshot. We require 30 team identities,
unique and contiguous official conference ranks, valid regular-season data, and
non-regressing overall games played. On failure, data.json is not modified.
"""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data.json'
SEASON = '2026-27'
SOURCE_PAGE = 'https://www.nba.com/standings?Season=2026-27&GroupBy=conf'
API_BASE = 'https://stats.nba.com/stats/leaguestandingsv3'
PARAMS = {'LeagueID':'00', 'Season':'2026-27', 'SeasonType':'Regular Season', 'Section':'overall'}
URL = API_BASE + '?' + urllib.parse.urlencode(PARAMS)
E = set('TOR MIA NYK PHI BOS CLE DET ORL IND WAS ATL CHI CHA MIL BKN'.split())
W = set('OKC SAS HOU DEN LAL UTA MIN PHX DAL POR GSW MEM LAC NOP SAC'.split())
TEAM_NAMES = {'hawks':'ATL','celtics':'BOS','nets':'BKN','hornets':'CHA','bulls':'CHI',
'cavaliers':'CLE','mavericks':'DAL','nuggets':'DEN','pistons':'DET','warriors':'GSW',
'rockets':'HOU','pacers':'IND','clippers':'LAC','lakers':'LAL','grizzlies':'MEM',
'heat':'MIA','bucks':'MIL','timberwolves':'MIN','pelicans':'NOP','knicks':'NYK',
 'thunder':'OKC','magic':'ORL','76ers':'PHI','suns':'PHX','trail blazers':'POR',
'kings':'SAC','spurs':'SAS','raptors':'TOR','jazz':'UTA','wizards':'WAS'}


def get_json(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36',
               'Accept':'application/json, text/plain, */*',
               'Accept-Language':'en-US,en;q=0.9',
               'Referer':'https://www.nba.com/', 'Origin':'https://www.nba.com',
               'x-nba-stats-origin':'stats', 'x-nba-stats-token':'true'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=24) as r:
        return json.load(r)


def standings_result(raw):
    results = raw.get('resultSets') or raw.get('resultSet')
    if isinstance(results, dict): results = [results]
    if not isinstance(results, list):
        raise ValueError('NBA stats did not return resultSets')
    table = next((x for x in results if str(x.get('name','')).lower()=='standings'), None)
    if not table: raise ValueError('NBA stats missing Standings table')
    headers = [str(h).strip().lower() for h in table['headers']]
    rows = table['rowSet']
    if len(rows)!=30: raise ValueError(f'Expected 30 NBA teams; got {len(rows)}')
    def cell(row,*names):
        for n in names:
            if n.lower() in headers:
                return row[headers.index(n.lower())]
        raise ValueError('Missing NBA field: '+str(names))
    result={'E':[],'W':[]}
    recs={}
    for row in rows:
        conf=str(cell(row,'Conference')).strip().lower()
        c = 'E' if conf in ('east','eastern') else 'W' if conf in ('west','western') else None
        if not c: raise ValueError(f'Unknown conference {conf}')
        name=str(cell(row,'TeamName')).strip().lower()
        code=TEAM_NAMES.get(name)
        if not code: raise ValueError('Unknown NBA team '+name)
        rank_value=cell(row,'PlayoffRank','ConferenceRank')
        try:
            rank=float(rank_value)
            if not rank.is_integer() or not 1 <= rank <= 15: raise ValueError()
            rank=int(rank)
        except (TypeError,ValueError):
            raise ValueError(f'Invalid official conference rank {rank_value} for {code}')
        wins=int(cell(row,'WINS'))
        losses=int(cell(row,'LOSSES'))
        if wins<0 or losses<0 or wins+losses>82:
            raise ValueError('Invalid NBA W/L record')
        result[c].append((rank,code))
        recs[code]={'wins':wins,'losses':losses}
    for c,allowed in (('E',E),('W',W)):
        teams=result[c]
        if {k for _,k in teams} != allowed or sorted(r for r,_ in teams)!=list(range(1,16)):
            raise ValueError(f'Non-unique or incomplete NBA {c} conference ranks')
        result[c]=[code for rank,code in sorted(teams)]
    return result,recs


def validate_not_regressed(previous, current):
    if not previous: return
    if previous.get('verification') != 'official': return
    for code,record in current.items():
        old=previous.get('records',{}).get(code)
        if old and record['wins']+record['losses'] < old['wins']+old['losses']:
            raise ValueError('Fresh data regressed games played for '+code)


def main():
    now=dt.datetime.now(ZoneInfo('Asia/Taipei'))
    today=now.date().isoformat()
    raw=get_json(URL)
    ranks,records=standings_result(raw)
    stored=json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'season':SEASON,'snapshots':[]}
    if stored.get('season') != SEASON: raise ValueError('Unexpected season in data.json')
    snaps=stored.get('snapshots',[])
    previous=max((x for x in snaps if x.get('verification')=='official' and x.get('date','')<=today),key=lambda x:x['date'],default=None)
    validate_not_regressed(previous,records)
    snapshot={'date':today,'E':ranks['E'],'W':ranks['W'],'source':'NBA Stats',
              'verification':'official','records':records,'sourceUrl':SOURCE_PAGE,
              'apiUrl':URL,'retrievedAt':now.isoformat(timespec='seconds')}
    # On success, retain prior history; latest date wins. Legacy ESPN records remain flagged unverified.
    snaps=[s for s in snaps if s.get('date')!=today]
    snaps.append(snapshot)
    stored.update({'season':SEASON,'sourceUrl':SOURCE_PAGE,'apiUrl':URL,
                   'lastUpdated':snapshot['retrievedAt'],'snapshots':sorted(snaps,key=lambda s:s['date'])})
    # Atomic write: failed fetch / validation never touches the existing file.
    tmp=OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(stored,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(tmp,OUT)
    print('NBA OFFICIAL',today,'E:',','.join(ranks['E']),'W:',','.join(ranks['W']))


if __name__=='__main__':
    main()
