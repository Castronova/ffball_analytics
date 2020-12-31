#!/usr/bin/env python3



import sys
import numpy
import pandas
import argparse


def build_team_season_df(data_files):

    dfs = []

    import pdb; pdb.set_trace()
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

#        df = df.T
#
#        df.rename(columns={'index': 'week'}, inplace=True)

        # store in list
        dfs.append(df)

    # combine dict list into new dataframe
    import pdb; pdb.set_trace()
    df = pandas.concat(dfs)

    return df



if __name__ == '__main__':
    p = argparse.ArgumentParser()
    s = p.add_subparsers(dest='parser_name')

    # parser for formatting data
    p1 = s.add_parser('format-data',
                      help='formats and builds dataframes for schedule analytics')
    p1.add_argument('-d', '--team-data-files', required=True, nargs='+',
                    help='space separated list of files that contain team statistic files, e.g. data/team-stats*')

    args = p.parse_args()

    if args.parser_name is None:
        p.print_help(sys.stderr)

    # format data operation
    if args.parser_name == 'format-data':
        # build team data df for all matching paths in --team-data-location
        df = build_team_season_df(args.team_data_files)
        

