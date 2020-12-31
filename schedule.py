#!/usr/bin/env python3



import sys
import numpy
import pandas
import argparse


def build_team_season_df(data_files):

    dfs = []

    for f in data_files:
        df = pandas.read_csv(f)

        # drop non-starters
        df = df[df['Lineup-Pos'] != 'BN']
        df = df[df['Lineup-Pos'] != 'Bye']

        # fix column datatypes
        df['Fan Pts'] = pandas.to_numeric(df['Fan Pts'])

        # aggregate by owner, sum 'Fan Pts'
        df = df.groupby(['owner']).agg({'Fan Pts': 'sum'})

        # add column for week of season
        df['week'] = f.split('-')[-1].split('.')[0]
        
        df = df.reset_index()
        df = df.pivot(index='week', columns='owner', values='Fan Pts')

        # store in list
        dfs.append(df)

    # combine dict list into new dataframe
    df = pandas.concat(dfs)

    return df



if __name__ == '__main__':
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest='parser_name')

    # parser for formatting data
    p1 = s.add_parser('format-data',
                      help='formats and builds dataframes for schedule analytics')
    p1.add_argument('-d', '--team-data-files', required=True, nargs='+',
                    help='space separated list of files that contain team' 
                         'statistic files, e.g. data/team-stats*')
    p1.add_argument('-o', '--outfile', default='weekly-team-totals.csv',
                    help='location to save output file')

    args = p.parse_args()

    if args.parser_name is None:
        p.print_help(sys.stderr)

    # format data operation
    if args.parser_name == 'format-data':

        # build team data df for all matching paths in --team-data-location
        df = build_team_season_df(args.team_data_files)

        df.to_csv(args.outfile)


        

