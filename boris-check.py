#!/usr/bin/env python


import os
import sys
import pandas
import requests
import argparse
import scrape
from tabulate import tabulate

dst_map = {
'New York Jets': 'New York Jets',
'Houston': 'Houston Texans',
'Tennessee': 'Tennessee Titans', 
'Denver': 'Denver Broncos', 
'Detroit': 'Detroit Lions', 
'Carolina': 'Carolina Panthers', 
'Tampa Bay': 'Tampa Bay Buccaneers',
'Miami': 'Miami Dolphins',
'New Orleans': 'New Orleans Saints',
'Los Angeles Rams': 'Los Angeles Rams',
'New York Giants': 'New York Giants',
'Cleveland': 'Cleveland Browns',
'Pittsburgh': 'Pittsburgh Steelers',
'Green Bay': 'Green Bay Packers',
'Washington': 'Washington Football Team',
'Seattle': 'Seattle Seahawks',
'Kansas City': 'Kansas City Chiefs',
'Baltimore': 'Baltimore Ravens',
'Indianapolis': 'Indianapolis Colts',
'Arizona': 'Arizona Cardinals',
'San Francisco': 'San Francisco 49ers',
'New England': 'New England Patriots',
'Dallas': 'Dallas Cowboys',
'Buffalo': 'Buffalo Bills',
'Los Angeles Chargers': 'Los Angeles Chargers',
'Philadelphia': 'Philadelphia Eagles',
'Minnesota': 'Minnesota Vikings',
'Cincinnati': 'Cincinnati Bengals',
'Jacksonville': 'Jacksonville Jaguars',
'Chicago': 'Chicago Bears',
'Atlanta': 'Atlanta Falcons',
'Las Vegas': 'Las Vegas Raiders',
  }

def get_roster(owner):
    driver = scrape.get_webdriver()
    managers = pandas.DataFrame(scrape.get_managers(driver))

    # exit if the manager is not found
    if owner not in managers['owner'].values:
        print(f'could not find {owner} in {managers["owner"]}') 
        sys.exit(1)
    manager = managers[managers.owner == 'Tony']
    ID = manager.teamid.iloc[0]
    OWNER = manager.owner.iloc[0]
#    print(f'Processing: {OWNER}, Week {week}', flush=True)
    
    return scrape.get_team_roster(driver, ID, OWNER)


def collect_tiers(week):

    data = []
    for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']:
        print(f'-> Collecting week {week} tiers: {pos}')
        r = requests.get(f'https://s3-us-west-1.amazonaws.com/fftiers/out/text_{pos}.txt')
        txt = r.text
        tier = 1
        for line in txt.split('\n'):
            players = line.split(':')[-1].split(',')
            for player in players:
                name = player.strip()
                if name != '':
                    data.append({'name': player.strip(),
                                 'tier': tier,
                                 'pos': pos})
            tier += 1

    df = pandas.DataFrame(data)
    df = df.rename({'DST':'DEF'})
    df.to_csv(f'data/week-{week}-tiers.csv',
              index=None)


def check_available_fas(fa, bo, roster):
    bo['available'] = False
    fas = fa.Name.values
    for index, row in bo.iterrows():
        if row.pos == 'DST':
            # do partial match
            if row['name'].split(' ')[0] in fas:
                bo.at[index, 'available'] = True
        elif row['name'] in fas:
            bo.at[index, 'available'] = True

    # add tiers to roster
    roster['tier'] = 999
    roster = roster.rename(str.lower, axis='columns')
    for index, row in roster.iterrows():
        name = row.iloc[0]
        value = bo[bo.name == name]
        if len(value) == 0:
            continue
        roster.loc[roster.name==name, 'tier'] = value.tier.iloc[0]
    roster.name = '*' + roster.name

    bo = bo[bo.available == True][['name', 'tier', 'pos']]

    if len(bo) == 0:
        print('No free agents on tier list')
    else:
        bo = bo.append(roster)
        for pos in bo.pos.unique():
            players = bo[bo.pos == pos].sort_values('tier')
            print('\n') 
            print(tabulate(players,
                           headers='keys',
                           tablefmt='psql', 
                           showindex=False))

            



if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--week', type=int, required=True,
                   help='the week to check')
    p.add_argument('--owner', default='Tony',
                   help='owner roster to compare')
    
    args = p.parse_args()
    

    fa_data_path = f'data/fa-stats-week-{args.week}.csv'
    tier_path = f'data/week-{args.week}-tiers.csv'

    # make output dir if it doesn't already exist
    if not os.path.exists('data'):
        os.makedirs('data')

    if not os.path.exists(tier_path):
        # collect data
        collect_tiers(args.week)

    if not os.path.exists(fa_data_path):
        print(f'Cannot locate free agent data in {fa_data_path}. Use `scrape.py` to collect data')
        sys.exit(1)

    df_fa = pandas.read_csv(fa_data_path)
    df_tier = pandas.read_csv(tier_path)
    roster = get_roster(args.owner)[['Name', 'Pos']]
    check_available_fas(df_fa, df_tier, roster)
