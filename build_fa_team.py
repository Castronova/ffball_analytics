#!/usr/bin/env python

import os
import sys
import pandas
from tabulate import tabulate
import argparse


def build_team(week):

    fpath = f'data/fa-stats-week-{week}.csv'
    if not os.path.exists(fpath):
        print(f'File not found: {fpath}. Make sure that data has been collected for this week')
        sys.exit(1)

    df = pandas.read_csv(fpath)
   
    team_pos = {'QB':1,
                'RB':2,
                'WR':3,
                'TE':1,
                'K':1,
                'DEF':1}
    players = []
    for k, v in team_pos.items():
        players.extend(list(df[df.Pos == k].Name[:v].values))

    team = df[df.Name.isin(players)][['Name','Pos','Fan Pts']]
    team['Fan Pts'] = team['Fan Pts'].astype(float)
    fa_pts = team['Fan Pts'].sum()

    # check to see who this team would've beaten
    team_df = pandas.read_csv(f'data/team-stats-week-{week}.csv')

    # subset only active roster players
    team_df = team_df[team_df['Lineup-Pos'] != 'BN'][['owner', 'Fan Pts']]
    team_df['Fan Pts'] = team_df['Fan Pts'].astype(float)
    team_df = team_df.groupby('owner').sum().reset_index()
    team_df = team_df.append({'owner':'Best-Of-The-Rest', 'Fan Pts': fa_pts},
                             ignore_index=True)
    team_df.sort_values(by='Fan Pts', ascending=False, inplace=True)
    team_df = team_df.rename(columns={'owner':'Owner', 'Fan Pts':'Pts'})
    team_df.reset_index(drop=True, inplace=True)
    team_df = team_df.set_index('Owner')

    return team, team_df


if __name__ == '__main__':

    p = argparse.ArgumentParser()
    p.add_argument('week', type=int,
                   help='week to build the team for')
    args = p.parse_args()

    team, team_df = build_team(args.week)

    print(f'\nWeek: {args.week} - Best-of-the-Rest Roster') 
    print(tabulate(team, headers='keys', tablefmt='psql', showindex=False))

    print(f'\nWeek: {args.week} - Point Totals') 
    print(tabulate(team_df, headers='keys', tablefmt='psql'))

    dfs = []
    for i in range(1, args.week+1):
        team, team_df = build_team(i)
        dfs.append(team_df)

    print(f'\nTotal Points Through Week {args.week}')
    print(tabulate(sum(dfs).sort_values(by='Pts', ascending=False), tablefmt='psql'))



