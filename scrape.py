#!/usr/bin/env python3

import os
import re
import time
import pandas
import argparse
import settings
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys


SLEEP_SECONDS = 2
END_WEEK = 1


def process_page_fa(html):
    # parse the html into a dataframe
    # matching any table that contains 'Pos'
    df = pandas.read_html(html, "Fan Pts")[0]

    # flatten and rename columns
    df.columns = [
        " ".join(col).strip()
        if ("Unnamed" not in col[0]) and ("Fantasy" not in col[0])
        else col[1]
        for col in df.columns.values
    ]
    df.drop(
        ["Action", "Forecast", "% Start"],
        axis=1,
        errors="ignore",
        inplace=True,
    )
    df.rename(
        columns={
            "Offense": "Name",
            "Kickers": "Name",
            "Defense/Special Teams": "Name",
            "Pos": "Lineup-Pos",
        },
        inplace=True,
        errors="ignore",
    )

    # generate pos col from df.Name.split('-')[1].split[' '][0]
    # create Pos column
    f = lambda x: x.split("-")[1].strip().split(" ")[0].strip()
    df["Pos"] = df.Name.apply(f)

    # clean name column
    f = lambda x: " ".join(x.split("-")[0].split(" ")[:-2])
    df["Name"] = df.Name.apply(f)
    expression = "\\b[pP]layer\\b|\\b[nN]otes?\\b|\\b[nN]o\\b|\\b[Nn]ew\\b"
    df.Name = df.Name.str.replace(expression, "", regex=True)
    df.Name = df.Name.str.strip()

    # drop rows where player name is None
    df = df[df.Name != ""]

    # fix special chars in Fan Pts header
    df = df.rename(columns=lambda x: re.sub("Fan Pts.*", "Fan Pts", x))

    return df


def login(driver):
    driver.get("https://login.yahoo.com/")

    username = driver.find_element_by_name("username")
    username.send_keys(settings.YAHOO_USERNAME)
    driver.find_element_by_id("login-signin").send_keys(Keys.RETURN)

    time.sleep(SLEEP_SECONDS)

    password = driver.find_element_by_name("password")
    password.send_keys(settings.YAHOO_PASSWORD)
    driver.find_element_by_id("login-signin").send_keys(Keys.RETURN)


def get_weekly_fa_stats(outfile, week, proj=False):

    driver = get_webdriver()
    dfs = []
    stat = f"S_PW_{week}" if proj else f"S_W_{week}"
    for pos in ["QB", "WR", "RB", "TE", "K", "DEF"]:
        print(f"Processing FA data for {pos} (week {week}, projected={proj})")
        try:
            url = (
                "https://football.fantasysports.yahoo.com/f1/"
                + f"{str(settings.YAHOO_LEAGUEID)}/players?"
                + f"status=A&pos={pos}&cut_type=9&stat1={stat}&"
                + "myteam=0&sort=PTS&sdir=1"
            )
            driver.get(url)
            dfs.append(process_page_fa(driver.page_source))
        except Exception as e:
            print("Failed to process page, sleeping and retrying", e)
            time.sleep(SLEEP_SECONDS * 5)
            dfs.append(process_page_fa(driver.page_source))

    # join dataframes together
    combined = pandas.concat(dfs, ignore_index=True, sort=False)
    combined.replace({"^-$": 0.0}, regex=True, inplace=True)
    combined.fillna(0, inplace=True)

    # replace any Fantasy Point values of '-'
    combined.loc[combined["Fan Pts"] == "-", "Fan Pts"] = 0.0

    # drop "Unnamed columns"
    combined = combined[
        combined.columns.drop(list(combined.filter(regex="Unnamed")))
    ]

    # save dataframe to csv
    combined.to_csv(outfile, index=False)

    driver.close()


def get_managers(driver):

    # get list of managers
    managers = "https://football.fantasysports.yahoo.com/f1/" + \
               f"{settings.YAHOO_LEAGUEID}/teams"
    driver.get(managers)
    table = driver.find_elements_by_xpath(
        "/html/body/div[1]/div[2]/div[2]/div[2]/div/div/div[2]/div[2]/section/div/div/div[3]/section/div/table"
    )
    rows = table[0].find_elements_by_tag_name("tr")

    managers = []
    for row in rows:
        td = row.find_elements_by_tag_name("td")
        if len(td) == 0:
            continue
        USER_ID = td[0].id
        TEAM_NAME = td[0].find_elements_by_tag_name("a")[-1].text
        TEAM_ID = td[1].get_attribute("id").split("-")[1]
        OWNER = td[1].text
        managers.append(
            dict(
                userid=USER_ID, teamname=TEAM_NAME, teamid=TEAM_ID, owner=OWNER
            )
        )
        print(f"{USER_ID}\t{TEAM_NAME}\t{TEAM_ID}\t{OWNER}")
    return managers


def get_webdriver():

    # Create web driver
    print("Creating WebDriver", flush=True)
    chrome_options = Options()
    chrome_options.add_argument("--headless")

    driver = webdriver.Chrome("./chromedriver", chrome_options=chrome_options)
    driver.set_page_load_timeout(30)

    print("Logging in", flush=True)
    login(driver)

    time.sleep(SLEEP_SECONDS)

    return driver


def get_weekly_team_stats(outfile, week=1):

    driver = get_webdriver()

    # get list of managers
    managers = get_managers(driver)

    # list to store weekly stats
    df_list = []

    # loop through each team and get weekly stats
    for manager in managers:

        # sleep to throttle requests
        time.sleep(SLEEP_SECONDS)

        ID = manager["teamid"]
        OWNER = manager["owner"]
        print(f"Processing: {OWNER}, Week {week}", flush=True)

        # build the url
        url = (
            "https://football.fantasysports.yahoo.com/f1/"
            + f"{settings.YAHOO_LEAGUEID}/{ID}/team?&week={week}"
        )

        # load the webpage
        driver.get(url)

        # get page source
        html = driver.page_source

        # parse the html into a dataframe
        # matching any table that contains 'Pos'
        dfs = pandas.read_html(html, "Pos")
        for df in dfs[0:3]:

            # flatten and rename columns
            df.columns = [
                " ".join(col).strip()
                if ("Unnamed" not in col[0]) and ("Fantasy" not in col[0])
                else col[1]
                for col in df.columns.values
            ]
            df.drop(
                ["Action", "Forecast", "% Start"],
                axis=1,
                errors="ignore",
                inplace=True,
            )
            df.rename(
                columns={
                    "Offense": "Name",
                    "Kickers": "Name",
                    "Defense/Special Teams": "Name",
                    "Pos": "Lineup-Pos",
                },
                inplace=True,
                errors="ignore",
            )
            # drop any row where the Name col is (Empty).
            # This occurs when a bench position is not filled.
            if len(df[df.Name.str.contains("Empty")]) > 0:
                df.drop(df[df.Name.str.contains("Empty")].index, inplace=True)

            # generate pos col from df.Name.split('-')[1].split[' '][0]
            # create Pos column
            f = lambda x: x.split(" - ")[-1].strip().split(" ")[0].strip()
            df["Pos"] = df.Name.apply(f)

            # clean name column
            f = lambda x: " ".join(x.split(" - ")[0].split(" ")[:-1])
            df["Name"] = df.Name.apply(f)
            expression = (
                "\\b[pP]layer\\b|\\b[nN]otes?\\b|\\b[nN]o\\b|\\b[Nn]ew\\b"
            )
            df.Name = df.Name.str.replace(expression, "", regex=True)
            df.Name = df.Name.str.strip()

            # add owner name and id to the dataframe
            df["owner-id"] = ID
            df["owner"] = OWNER

            # replace any Fantasy Point values of 'Bye'
            df.loc[df["Fan Pts"] == "Bye", "Fan Pts"] = 0.0
            df.loc[df["Proj Pts"] == "Bye", "Proj Pts"] = 0.0

            # drop unnamed columns
            df = df[df.columns.drop(list(df.filter(regex="Unnamed")))]

            # save to data list
            df_list.append(df)

    # join dataframes together
    combined = pandas.concat(df_list, ignore_index=True, sort=False)
    combined.replace({"^-$": 0.0}, regex=True, inplace=True)
    combined.fillna(0, inplace=True)

    # save dataframe to csv
    combined.to_csv(outfile)

    driver.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        "--team-stats",
        action="store_true",
        help="indicates that team stats should be collected",
    )
    p.add_argument(
        "--fa-stats",
        action="store_true",
        help="indicates that free agent stats should be collected",
    )
    p.add_argument(
        "--week-start",
        required=True,
        type=int,
        help="week to begin collecting data for",
    )
    p.add_argument(
        "--week-end",
        default=None,
        type=int,
        help="week to end collecting data for. "
        "Defaults to --week-start if not provided",
    )
    p.add_argument(
        "--output-dir", default="./data", help="directory to save output data"
    )
    p.add_argument(
        "--proj",
        action="store_true",
        default=False,
        help="indicates the projected fa data should be downloaded. "
        "Note this only applies to the --fa-stats option",
    )

    args = p.parse_args()

    if not args.team_stats and not args.fa_stats:
        print(
            "Missing stats argument. "
            "Must indicate one of [--team-stats, --fa-stats]"
        )
        p.print_usage()

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)

    start_week = args.week_start
    end_week = (
        args.week_end + 1 if args.week_end is not None else start_week + 1
    )

    if args.team_stats:
        for week in range(start_week, end_week):
            outfile = os.path.join(
                args.output_dir, f"team-stats-week-{week}.csv"
            )
            get_weekly_team_stats(outfile, week)
    if args.fa_stats:
        for week in range(start_week, end_week):
            outfile = os.path.join(
                args.output_dir, f"fa-stats-week-{week}.csv"
            )
            get_weekly_fa_stats(outfile, week, args.proj)
