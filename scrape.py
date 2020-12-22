#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

import time, re, csv, sys, random

import pandas
import pickle

import settings

import time
import os
import re

import argparse


RE_REMOVE_HTML = re.compile('<.+?>')

SLEEP_SECONDS = 2
END_WEEK = 1
PAGES_PER_WEEK = 4
YAHOO_RESULTS_PER_PAGE = 25 # Static but used to calculate offsets for loading new pages

## todo: move to settings file
#league_id = '376023'

# Modify these as necessary based on league settings
fields = ['week', 'name', 'position', 'team', 'opp', 'bye_week',
    'passing_yds', 'passing_tds', 'passing_int',
    'rushing_att', 'rushing_yds', 'rushing_tds',
    'receiving_tgt', 'receiving_rec', 'receiving_yds', 'receiving_tds',
    'return_tds', 'twopt', 'fumbles', 'points', 'pct_owned']

# TODO: Try to get these automatically
XPATH_MAP = {
    'name': 'td[contains(@class,"player")]/div/div/div[contains(@class,"ysf-player-name")]/a',
    'position': 'td[contains(@class,"player")]/div/div/div[contains(@class,"ysf-player-name")]/span',
    'opp': 'td//div[contains(@class,"ysf-player-detail")]/span/a',

    'passing_yds': 'td[11]',
    'passing_tds': 'td[12]',
    'passing_int': 'td[13]',

    'rushing_att': 'td[14]',
    'rushing_yds': 'td[15]',
    'rushing_tds': 'td[16]',

    'receiving_tgt': 'td[17]',
    'receiving_rec': 'td[18]',
    'receiving_yds': 'td[19]',
    'receiving_tds': 'td[20]',

    'return_tds': 'td[21]',
    'twopt': 'td[22]',
    'fumbles': 'td[23]',
    
    'bye_week': 'td[6]',
    'points': 'td[7]',
    'pct_owned': 'td[8]',    
}

stats = []

def process_stats_row(stat_row, week):
    stats_item = {}
    stats_item['week'] = week
    for col_name, xpath in XPATH_MAP.items():
        stats_item[col_name] = RE_REMOVE_HTML.sub('', stat_row.find_element_by_xpath(xpath).get_attribute('innerHTML'))
    # Custom logic for team, position, and opponent
    stats_item['opp'] = stats_item['opp'].split(' ')[-1]
    team, position = stats_item['position'].split(' - ')
    stats_item['position'] = position
    stats_item['team'] = team
    return stats_item

def process_page(driver, week, cnt, pos):
    import pdb; pdb.set_trace()
    print('Getting stats for week', week, 'count', cnt)

    url = 'http://football.fantasysports.yahoo.com/f1/%s/players?status=A&pos=O&cut_type=9&stat1=S_PW_%d&myteam=0&pos=%d&sort=PR&sdir=1&count=%d' % (str(settings.YAHOO_LEAGUEID), week, pos, cnt)
    
    driver.get(url)

    base_xpath = "//div[contains(concat(' ',normalize-space(@class),' '),' players ')]/table/tbody/tr"

    rows = driver.find_elements_by_xpath(base_xpath)

    stats = []
    for row in rows:
        stats_item = process_stats_row(row, week)
        stats.append(stats_item)

    driver.find_element_by_tag_name('body').send_keys(Keys.END)

    print('Sleeping for', SLEEP_SECONDS)
    time.sleep(random.randint(SLEEP_SECONDS, SLEEP_SECONDS * 2))
    return stats

def process_page_fa(html):
    # parse the html into a dataframe
    # matching any table that contains 'Pos'
    df = pandas.read_html(html, 'Fan Pts')[0]

    # flatten and rename columns
    df.columns = [' '.join(col).strip() if ('Unnamed' not in col[0]) \
                  and ('Fantasy' not in col[0]) else col[1] \
                  for col in df.columns.values]
    df.drop(['Action', 'Forecast', '% Start'],
            axis=1,
            errors='ignore',
            inplace=True)
    df.rename(columns={'Offense':'Name',
                       'Kickers':'Name',
                       'Defense/Special Teams': 'Name',
                       'Pos':'Lineup-Pos'},
                       inplace=True, errors='ignore')
    
    # generate pos col from df.Name.split('-')[1].split[' '][0]
    # create Pos column
    f = lambda x: x.split('-')[1].strip().split(' ')[0].strip()
    df['Pos'] = df.Name.apply(f)

    # clean name column
    f = lambda x: ' '.join(x.split('-')[0].split(' ')[:-2])
    df["Name"] = df.Name.apply(f)
    expression = '\\b[pP]layer\\b|\\b[nN]otes?\\b|\\b[nN]o\\b|\\b[Nn]ew\\b'
    df.Name = df.Name.str.replace(expression, '', regex=True)
    df.Name = df.Name.str.strip()

    # drop rows where player name is None
    df = df[df.Name != '']

    # fix special chars in Fan Pts header
    df = df.rename(columns=lambda x: re.sub('Fan Pts.*','Fan Pts',x))

    return df


def login(driver):
    driver.get("https://login.yahoo.com/")

    username = driver.find_element_by_name('username')
    username.send_keys(settings.YAHOO_USERNAME)
    driver.find_element_by_id("login-signin").send_keys(Keys.RETURN)

    time.sleep(SLEEP_SECONDS)

    password = driver.find_element_by_name('password')
    password.send_keys(settings.YAHOO_PASSWORD)
    driver.find_element_by_id("login-signin").send_keys(Keys.RETURN)

def write_stats(stats, out):
    import pdb; pdb.set_trace()
    print('Writing to file', out)
    with open(out, 'w') as f:
        w = csv.DictWriter(f, delimiter=',', fieldnames=fields)
        w.writeheader()
        w.writerows(stats)

def get_weekly_fa_stats(outfile, week, proj=False):

    driver = get_webdriver()
    stats = []
    dfs = []
    stat = f'S_PW_{week}' if proj else f'S_W_{week}'
    for pos in ['QB', 'WR', 'RB', 'TE', 'K', 'DEF']:
        print(f'Processing FA data for {pos} (week {week}, projected={proj})')
        try:
            url = f'https://football.fantasysports.yahoo.com/f1/' + \
                  f'{str(settings.YAHOO_LEAGUEID)}/players?' + \
                  f'status=A&pos={pos}&cut_type=9&stat1={stat}&' + \
                  'myteam=0&sort=PTS&sdir=1'
            driver.get(url)
            dfs.append(process_page_fa(driver.page_source))
        except Exception as e:
            print('Failed to process page, sleeping and retrying', e)
            time.sleep(SLEEP_SECONDS * 5)
            dfs.append(process_page_fa(driver.page_source))
    
    # join dataframes together
    combined = pandas.concat(dfs, ignore_index=True, sort=False)
    combined.replace({'^-$': 0.0}, regex=True, inplace=True)
    combined.fillna(0, inplace=True)
            
    # replace any Fantasy Point values of '-'
    combined.loc[combined['Fan Pts'] == '-', 'Fan Pts'] = 0.
    
    # drop "Unnamed columns"
    combined = combined[combined.columns.drop(list(combined.filter(regex='Unnamed')))]

    # save dataframe to csv
    combined.to_csv(outfile, index=False)

    driver.close()

def get_managers(driver):
   

    # get list of managers
    managers = f'https://football.fantasysports.yahoo.com/f1/{settings.YAHOO_LEAGUEID}/teams'
    driver.get(managers)
    table = driver.find_elements_by_xpath('/html/body/div[1]/div[2]/div[2]/div[2]/div/div/div[2]/div[2]/section/div/div/div[3]/section/div/table')
    rows = table[0].find_elements_by_tag_name('tr')

    managers = []
    for row in rows:
        td = row.find_elements_by_tag_name('td')
        if len(td) == 0:
            continue
        USER_ID = td[0].id
        TEAM_NAME = td[0].find_elements_by_tag_name('a')[-1].text
        TEAM_ID = td[1].get_attribute('id').split('-')[1]
        OWNER = td[1].text
        managers.append(dict(userid=USER_ID,
                             teamname=TEAM_NAME,
                             teamid=TEAM_ID,
                             owner=OWNER))
        print(f'{USER_ID}\t{TEAM_NAME}\t{TEAM_ID}\t{OWNER}')
    return managers

def get_webdriver():
    
    # Create web driver
    print('Creating WebDriver', flush=True)
    chrome_options = Options()
#    chrome_options.add_extension('chrome-ublock.crx')
#    chrome_options.add_argument("--enable-extensions")
    chrome_options.add_argument("--headless")

    driver = webdriver.Chrome('./chromedriver', chrome_options=chrome_options)
    driver.set_page_load_timeout(30)

    print("Logging in", flush=True)
    login(driver)

    time.sleep(SLEEP_SECONDS)
    
    return driver


def get_team_roster(driver, team_id, owner, week=None):

    print(f'Processing: {owner}, Week {week}', flush=True)

    # build the url
    url = f'https://football.fantasysports.yahoo.com/f1/{settings.YAHOO_LEAGUEID}/{team_id}/team'
    if week is not None:
        url += f'?&week={week}'

    # load the webpage
    driver.get(url)
    df_list = []

    # get page source
    html = driver.page_source
     
    # parse the html into a dataframe
    # matching any table that contains 'Pos'
    dfs = pandas.read_html(html, 'Pos')
    for df in dfs[0:3]:
    
        # flatten and rename columns
        df.columns = [' '.join(col).strip() if ('Unnamed' not in col[0]) \
                      and ('Fantasy' not in col[0]) else col[1] \
                      for col in df.columns.values]
        df.drop(['Action', 'Forecast', '% Start'],
                axis=1,
                errors='ignore',
                inplace=True)
        df.rename(columns={'Offense':'Name',
                           'Kickers':'Name',
                           'Defense/Special Teams': 'Name',
                           'Pos':'Lineup-Pos'},
                           inplace=True, errors='ignore')
        # drop any row where the Name col is (Empty). This occurs when a bench position is not filled.
        #df = df.loc[~df.Name.str.contains('Empty')].copy()
        if len(df[df.Name.str.contains('Empty')]) > 0:
            df.drop(df[df.Name.str.contains('Empty')].index, inplace=True)

        # generate pos col from df.Name.split('-')[1].split[' '][0]
        # create Pos column
        f = lambda x: x.split(' - ')[-1].strip().split(' ')[0].strip()
        df['Pos'] = df.Name.apply(f)

        # clean name column
        f = lambda x: ' '.join(x.split(' - ')[0].split(' ')[:-1])
        df["Name"] = df.Name.apply(f)
        expression = '\\b[pP]layer\\b|\\b[nN]otes?\\b|\\b[nN]o\\b|\\b[Nn]ew\\b'
        df.Name = df.Name.str.replace(expression, '', regex=True)
        df.Name = df.Name.str.strip()
        
        # add owner name and id to the dataframe
        df['owner-id'] = team_id
        df['owner'] = owner


        # save to data list
        df_list.append(df)

    # join dataframes together
    combined = pandas.concat(df_list, ignore_index=True, sort=False)
    combined.replace({'^-$': 0.0}, regex=True, inplace=True)
    combined.fillna(0, inplace=True)

    driver.close()

    return combined

        

def get_weekly_team_stats(outfile, week=1):

#    # create directory for output data
#    if not os.path.exists('data'):
#        os.mkdir('data')

    driver = get_webdriver()

    # get list of managers
    managers = get_managers(driver)

#    df = pandas.DataFrame()
#    if os.path.exists('weekly-data.pkl'):
#        df = pandas.read_pickle('weekly-data.pkl')
    
#    # get team stats for each week
#    for WEEK in weeks:

    # list to store weekly stats
    df_list = []

#        # define object to store header labels
#        headers = {}
#
#        if not df.empty:
#            if OWNER in df.owner.unique():
#                print(f'skipping data collection for {OWNER}')
#                continue

    # loop through each team and get weekly stats
    for manager in managers:

        # sleep to throttle requests
        time.sleep(SLEEP_SECONDS)

        ID = manager['teamid']
        OWNER = manager['owner']
        print(f'Processing: {OWNER}, Week {week}', flush=True)


        # build the url
        url = f'https://football.fantasysports.yahoo.com/f1/{settings.YAHOO_LEAGUEID}/{ID}/team?&week={week}'

        # load the webpage
        driver.get(url)
        
        # get page source
        html = driver.page_source
        
        # parse the html into a dataframe
        # matching any table that contains 'Pos'
        dfs = pandas.read_html(html, 'Pos')
        for df in dfs[0:3]:
        
            # flatten and rename columns
            df.columns = [' '.join(col).strip() if ('Unnamed' not in col[0]) \
                          and ('Fantasy' not in col[0]) else col[1] \
                          for col in df.columns.values]
            df.drop(['Action', 'Forecast', '% Start'],
                    axis=1,
                    errors='ignore',
                    inplace=True)
            df.rename(columns={'Offense':'Name',
                               'Kickers':'Name',
                               'Defense/Special Teams': 'Name',
                               'Pos':'Lineup-Pos'},
                               inplace=True, errors='ignore')
            # drop any row where the Name col is (Empty). This occurs when a bench position is not filled.
            #df = df.loc[~df.Name.str.contains('Empty')].copy()
            if len(df[df.Name.str.contains('Empty')]) > 0:
                df.drop(df[df.Name.str.contains('Empty')].index, inplace=True)

            # generate pos col from df.Name.split('-')[1].split[' '][0]
            # create Pos column
            f = lambda x: x.split(' - ')[-1].strip().split(' ')[0].strip()
            df['Pos'] = df.Name.apply(f)

            # clean name column
            f = lambda x: ' '.join(x.split(' - ')[0].split(' ')[:-1])
            df["Name"] = df.Name.apply(f)
            expression = '\\b[pP]layer\\b|\\b[nN]otes?\\b|\\b[nN]o\\b|\\b[Nn]ew\\b'
            df.Name = df.Name.str.replace(expression, '', regex=True)
            df.Name = df.Name.str.strip()
            
            # add owner name and id to the dataframe
            df['owner-id'] = ID
            df['owner'] = OWNER

            # replace any Fantasy Point values of 'Bye'
            df.loc[df['Fan Pts'] == 'Bye', 'Fan Pts'] = 0.
            df.loc[df['Proj Pts'] == 'Bye', 'Proj Pts'] = 0.
   
            # drop unnamed columns
            df = df[df.columns.drop(list(df.filter(regex='Unnamed')))]

            # save to data list
            df_list.append(df)
        
    # join dataframes together
    combined = pandas.concat(df_list, ignore_index=True, sort=False)
    combined.replace({'^-$': 0.0}, regex=True, inplace=True)
    combined.fillna(0, inplace=True)

    # save dataframe to csv
    combined.to_csv(outfile)
    #combined.to_csv(f'data/stats-week-{WEEK}.csv', index=False)

    driver.close()
           
#            # loop through roster tables
#            for ti in range(1, 4):
#                try:
#                    table = driver.find_elements_by_xpath(f'/html/body/div[1]/div[2]/div[2]/div[2]/div/div/div[2]/div[2]/section/div/div/div[3]/section[1]/div/section/div[{ti}]/table')[0]
#                    rows = table.find_elements_by_tag_name('tr')
#                except Exception as e:
#                    print(e)
#                    continue
#
#                for row in rows:
#                    tds = row.find_elements_by_tag_name('td')
#
#                    # skip header rows
#                    if len(tds) == 0:
#                        header = row.find_elements_by_tag_name('th')
#                        if header[0].text == 'Pos':
#                            idx = 0
#                            for h in range(0, len(header)):
#                                val = header[h].text
#                                if val == 'Action':
#                                    # increment 1 extra b/c this is really 2 columns
#                                    idx += 1
#                                if val.strip() != '':
#                                    headers[val] = idx
#                                idx += 1
#                        continue
#                    offense_statline = {'pass-yds': 9,
#                                        'pass-td': 10,
#                                        'pass-int': 11,
#                                        'rush-att': 12,
#                                        'rush-yds': 13,
#                                        'rush-td': 14,
#                                        'recv-tgt': 15,
#                                        'recv-rec': 16,
#                                        'recv-yds': 17,
#                                        'recv-td': 18,
#                                        'ret-td': 19,
#                                        'misc-2pt': 20,
#                                        'fum-lost': 21
#                                        }
#                    defense_statline = {'pts-vs': 8,
#                                        'sack': 9,
#                                        'safe': 10,
#                                        'int': 11,
#                                        'fum-rec': 12,
#                                        'td': 13,
#                                        'blk-kick': 14,
#                                        }
#                    kicker_statline = {'0-19': 8,
#                                       '20-29': 9,
#                                       '30-39': 10,
#                                       '40-49': 11,
#                                       '50+': 12,
#                                       'pat-made': 13,
#                                        }
#                    ROSPOS = tds[0].text
#                    PLAYER = tds[1].text.split('-')[0].strip()
#                    POS = tds[1].text.split('\n')[0].split('-')[-1].strip()
#                    PTS = tds[headers['Fan Pts']].text
#                    EST = tds[headers['Proj Pts']].text
#                    dat = dict(position=POS,
#                               rosterpos=ROSPOS,
#                               player=PLAYER,
#                               points=PTS,
#                               week=WEEK,
#                               owner=OWNER)
#                    if ROSPOS == 'K':
#                        for k, v in kicker_statline.items():
#                            val = tds[v].text
#                            dat.update({k: val})
#                    elif ROSPOS == 'DEF':
#                        for k, v in defense_statline.items():
#                            val = tds[v].text
#                            dat.update({k: val})
#                    else:
#                        for k, v in offense_statline.items():
#                            val = tds[v].text
#                            dat.update({k: val})
#                    data.append(dat)
#        
#        print('Saving data')
#        df = df.append(pandas.DataFrame(data))
#        with open('weekly-data.pkl', 'wb') as f:
#            pickle.dump(df, f)
#    
#    driver.close()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--team-stats', action='store_true',
                   help='indicates that team stats should be collected')
    p.add_argument('--fa-stats', action='store_true',
                   help='indicates that free agent stats should be collected')
    p.add_argument('--week-start', required=True, type=int,
                   help='week to begin collecting data for')
    p.add_argument('--week-end', default=None, type=int,
                   help='week to end collecting data for. Defaults to --week-start if not provided')
    p.add_argument('--output-dir', default='./data',
                   help='directory to save output data')
    p.add_argument('--proj', action='store_true', default=False,
                   help='indicates the projected fa data should be downloaded. Note this only applies to the --fa-stats option')

    args = p.parse_args()
    
    if not args.team_stats and not args.fa_stats:
        print('Missing stats argument. Must indicate one of [--team-stats, --fa-stats]')
        p.print_usage()

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)

    start_week = args.week_start
    end_week = args.week_end + 1 if args.week_end is not None else start_week + 1

    if args.team_stats:
        for week in range(start_week, end_week):
            outfile = os.path.join(args.output_dir, f'team-stats-week-{week}.csv')
            get_weekly_team_stats(outfile, week)
    if args.fa_stats:
        for week in range(start_week, end_week):
            outfile = os.path.join(args.output_dir, f'fa-stats-week-{week}.csv')
            get_weekly_fa_stats(outfile, week, args.proj)
    


#    outfile = 'stats.csv'
#    week = range(1, 15)
#    if len(sys.argv) > 1:
#        outfile = sys.argv[1]
#        week = sys.argv[2]
#
#    get_weekly_stats(outfile, week)
