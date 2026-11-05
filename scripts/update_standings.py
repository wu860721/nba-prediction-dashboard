#!/usr/bin/env python3
"""Fetch NBA conference standings from ESPN, validate and append one daily snapshot."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data.json'
URL = 'https://site.api.espn.com/apis/v2/sports/basketball/nba/standings?season=2027&type=0&limit=100'
E = set('TOR MIA NYK PHI BOS CLE DET ORL IND WAS ATL CHI CHA MIL BKN'.split())
W = set('OKC SAS HOU DEN LAL UTA MIN PHX DAL POR GSW MEM LAC NOP SAC'.split())
ALIASES = {'WSH': 'WAS', 'SA': 'SAS', 'GS': 'GSW', 'NY': 'NYK', 'NO': 'NOP', 'UTAH': 'UTA'}


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; NBA-Prediction-Tracker/1.0)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.load(response)


def normalize(code):
    s = (code or '').upper().strip()
    return ALIASES.get(s, s)


def descendants(node):
    yield node
    for child in node.get('children', []) or []:
        yield from descendants(child)


def conference_entries(raw):
    result = {}
    for group in descendants(raw):
        name = (group.get('name') or group.get('displayName') or '').lower()
        abbr = (group.get('abbreviation') or '').lower()
        if ('eastern conference' in name or 'western conference' in name or name in ('east', 'west') or abbr in ('east', 'west')):
            conf = 'E' if ('east' in name or abbr == 'east') else 'W'
            entries = (group.get('standings') or {}).get('entries') or []
            if len(entries) != 15:
                continue
            ranked = []
            for index, entry in enumerate(entries):
                team = entry.get('team') or {}
                code = normalize(team.get('abbreviation'))
                stats = entry.get('stats') or []
                # ESPN may provide ordinal team seeding; use it only if all 15 valid.
                seed = None
                for stat in stats:
                    if stat.get('name') in ('playoffSeed', 'rank') or stat.get('abbreviation') == 'SEED':
                        try:
                            n = int(float(stat.get('value', stat.get('displayValue'))))
                            if 1 <= n <= 15: seed = n
                        except (TypeError, ValueError):
                            pass
                ranked.append((code, seed, index))
            codes = [r[0] for r in ranked]
            if set(codes) != (E if conf == 'E' else W):
                continue
            seeds = [r[1] for r in ranked]
            if set(seeds) == set(range(1,16)):
                ranked.sort(key=lambda r: r[1])
            result[conf] = [r[0] for r in ranked]
    if set(result) != {'E', 'W'}:
        raise ValueError('ESPN did not return 15 complete teams in both conference standings; refusing to save incomplete data.')
    return result


def main():
    now = dt.datetime.now(ZoneInfo('Asia/Taipei'))
    today = now.strftime('%Y-%m-%d')
    data = get_json(URL)
    ranks = conference_entries(data)
    stored = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {'season':'2026-27','snapshots':[]}
    snaps = [s for s in stored.get('snapshots',[]) if s.get('date') != today]
    snaps.append({'date':today, 'E':ranks['E'], 'W':ranks['W'], 'source':'ESPN', 'retrievedAt':now.isoformat(timespec='seconds')})
    stored.update({'season':'2026-27','sourceUrl':URL,'lastUpdated':now.isoformat(timespec='seconds'),'snapshots':sorted(snaps,key=lambda s:s['date'])})
    OUT.write_text(json.dumps(stored,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Updated', today, 'E:', ','.join(ranks['E']), 'W:', ','.join(ranks['W']))

if __name__=='__main__':
    main()
