"""
Fantasy_Football_Server_Initialization_v1.1
v1.0: first version
v1.1: added score predictions from scores

author: Brock Ricker
GitHub: https://github.com/brock-ricker
07/02/2022

This script pulls data from multiple sources and uses it to set-up SQLite server on your local machine. 

Main sources of data: 
    *APIs from myfantasyleague.com for fantasy football data
    *Web scraping from https://www.sportsoddshistory.com/ for historical scores, spreads and over/unders

Separate versions of these functions can also be found ony my GitHub
"""

#import necesarry modules here
import pandas as pd
import numpy as np
import requests
import json
import bs4
from sqlalchemy import create_engine
import time
import logging
import tkinter as tk
import tkinter.filedialog as fd
import os


"""
***Main Function***
Pulls from APIs, Scraps data, cleans tables, and exports to SQLite server
"""

def main():

    #tkinter widgets for server setup
    
    #server/API info
    master = tk.Tk()
    info = GetEntry(master)
    master.mainloop()

    #define user agent for my fantasy API use
    agent = info.agent
    #my Fantasy League, League ID
    league_id = info.league_id
    #create db name - this will be SQLite
    db_name = info.db_name
    #Years of league history
    temp_years = info.years.split(",")

    #converting input years list to proper list
    years = []
    for year in temp_years:
        years.append(int(year.strip()))

    #file location
    master=tk.Tk()
    server_location = fd.askdirectory(title="Choose Server Location")
    master.destroy()

    #setting working directory
    os.chdir(server_location)

    #setup logging info
    #naming log based on date/time
    t=time.localtime()
    date = time.strftime("%y%m%d_%H%M%S", t)
    #logging settings
    logging.basicConfig(filename=f"{date}.log", encoding='utf-8', level=logging.INFO)
    #initialize errors variable = False
    errors = False

    try:
        # create sqlite engine for a db using name defined above
        engine = create_engine(f"sqlite:///{db_name}.db", echo=False)
        #create connection to the engine
        conn = engine.connect()
        logging.info("successfully creates SQLite DB")
    except Exception as Argument:
        logging.exception(f"Error occurred while creating SQLite db @{server_location}")
        errors = True

    #pulling weekly scores
    try:
        weekly_score_pull(years,agent,conn,league_id)
    except Exception as Argument:
        logging.exception(f"***Error occurred while attempting to pull weekly scores")
        errors = True

    #pulling simple player info
    try:
        simple_player_pull(years,agent,conn,league_id)
    except Exception as Argument:
        logging.exception(f"***Error occurred while attempting to pull player info")
        errors = True
    
    #pulling ADP info
    try:
        adp_pull(years,agent,conn)
    except Exception as Argument:
        logging.exception(f"***Error occurred while attempting to pull ADP info")
        errors = True

    """"
    Rookie ADP to go here in the future when missing data bug is resolved
    #pulling Rookie ADP info
    try:
        rookie_adp_pull(years)
    except Exception as Argument:
        logging.exception(f"Error occurred while attempting to pull Rookie ADP info")
        errors = True
    """
    #pulling points allowed info
    try:
        points_allowed_pull(years,agent,conn,league_id)
    except Exception as Argument:
        logging.exception(f"***Error occurred while attempting to pull points allowed info")
        errors = True

    #pulling projected points info
    try:
        projected_scores_pull(years,agent,conn,league_id)
    except Exception as Argument:
        logging.exception(f"***Error occurred while attempting to pull projected scores info")
        errors = True

    #pulling league info
    try:
        league_teams_pull(years,agent,conn,league_id)
    except Exception as Argument:
        logging.exception(f"***Error occurred while attempting to pull league team info")
        errors = True

    #scrapping spreads
    try:
        spread_scraper(years,conn)
    except Exception as Argument:
        logging.exception(f"***Error occurred while attempting to scrape for spreads")
        errors = True

    if errors == True:
        msg = f"There was an error with your server setup, please view the log: {date}"
    else:
        msg = "The setup completed successfully"
    
    popup = tk.Tk()
    popup.wm_title("!")
    label = tk.Label(popup, text=msg)
    label.pack(side="top", fill="x", pady=10)
    B1 = tk.Button(popup, text="Okay", command = popup.destroy)
    B1.pack()
    popup.mainloop()



"""
***Define all other functions here***
Pulls from APIs, Scraps data, cleans tables, and exports to SQLite server
"""

#defining pause function (for pause time between yearly API pulls)
def pause(t=2):
    time.sleep(t)

#defining pause function (for pause time between weekly API pulls)
def short_pause():
    time.sleep(1)

#define function for cleaning players table
def df_players_cleaner(df_players):

    df_players = df_players.astype({
        "id": int,
        "shouldStart": int,
        "score": float
    })

    df_players = df_players.rename(columns = {"shouldStart": "should_start"})

    return df_players

#define function for cleaning df_teams
def df_team_cleaner(df_teams):
    
    df_teams.drop(columns = ["player","comments"],inplace=True)
    
    df_teams = df_teams.astype({
        "score": float,
        "isHome": int,
        "id": int,
    })

    df_teams = df_teams.rename(columns = {"isHome": "is_home"})

    return df_teams

#define function for creating matchups table - !must run df_team_cleaner first!
def matchup_table_generator(df_teams):
    
    total_teams = len(df_teams)
    team1 = list(range(0,total_teams-1,2))
    team2 = list(range(1,total_teams,2))

    df_matchups = pd.DataFrame({
        "team1_id":list(df_teams.iloc[team1]["id"]),
        "team1_score":list(df_teams.iloc[team1]["score"]),
        "team2_id":list(df_teams.iloc[team2]["id"]),
        "team2_score":list(df_teams.iloc[team2]["score"])
    })

    df_matchups['winning_team'] = np.select([df_matchups['team1_score'] > df_matchups['team2_score'], df_matchups['team1_score'] < df_matchups['team2_score']], [df_matchups["team1_id"],df_matchups["team2_id"]], default="error")

    return df_matchups

#pulls weekly score data and saves to SQL server
#creates following tables: weekly_players, weekly_teams, weekly_matchup
def weekly_score_pull(years,agent,conn,league_id):
    logging.info("----------------------------------------weekly_score_pull----------------------------------------")
    i = 1
    for year in years:
        if i>1:
            pause()
        
        logging.info(f"begin parsing year: {year}")

        request_url = f"https://www54.myfantasyleague.com/{year}/export?L={league_id}&W=YTD&TYPE=weeklyResults&JSON=1&{agent}"
        req = requests.get(request_url)
        logging.info(f"connection results: {req}")
        req_data = req.json()
            
        weekly_results = req_data['allWeeklyResults']['weeklyResults']

        for single_week in weekly_results:
            if "matchup" not in single_week:
                break
            df_players = pd.json_normalize(single_week["matchup"],record_path=["franchise","player"])
            df_teams = pd.json_normalize(single_week["matchup"],record_path=["franchise"])
            
            #cleaning tables
            df_players = df_players_cleaner(df_players)
            df_teams = df_team_cleaner(df_teams)
            df_matchups = matchup_table_generator(df_teams)

            #adding weeks, years, regular_season to data_tables
            df_players["week"] = int(single_week["week"])
            df_players["year"] = year
            df_players["regular_season"] = int(single_week["matchup"][0]["regularSeason"])
            
            df_teams["week"] = int(single_week["week"])
            df_teams["year"] = year
            df_teams["regular_season"] = int(single_week["matchup"][0]["regularSeason"])
            
            df_matchups["week"] = int(single_week["week"])
            df_matchups["year"] = year
            df_matchups["regular_season"] = int(single_week["matchup"][0]["regularSeason"])        

            #writting to SQL
            df_players.to_sql("weekly_players", conn, if_exists="append");
            df_teams.to_sql("weekly_teams", conn, if_exists="append");
            df_matchups.to_sql("weekly_matchup", conn, if_exists="append");
            week = single_week["week"]
            logging.info(f"finished year: {year}, week: {week}")
        
        i = i+1

#cleans simple player data 
def clean_simple_players(players):
    players = players.astype({"id":int})
    players.rename(columns = {"status":"rookie"},inplace = True)
    players["rookie"].replace({"R":"yes"},inplace = True)
    players["rookie"].fillna("No", inplace= True)
    return players

#pulls player data and saves to SQL server
#creates following table: simple_players
def simple_player_pull (years,agent,conn,league_id):
    logging.info("----------------------------------------simple_player_pull----------------------------------------")
    i = 1
    for year in years:
        if i>1:
            pause()
            
        logging.info(f"begin parsing year: {year}")
        request_url = f"https://www54.myfantasyleague.com/{year}/export?L={league_id}&TYPE=players&JSON=1&{agent}"
        req = requests.get(request_url)
        req_data = req.json()
        logging.info(f"connection results: {req}")
        
        players = pd.json_normalize(req_data["players"],record_path=["player"])
        
        players = clean_simple_players(players)
        players["year"] = year
        
        players.to_sql("simple_players", conn, if_exists="append")
        i =i+1

#cleans ADP data
def clean_adp(adp):
    adp = adp.astype({
        'minPick':int, 
        'maxPick':int, 
        'draftsSelectedIn':int, 
        'id':int, 
        'averagePick':float, 
        'rank':int,
        'draftSelPct':int
    })
    return adp

#pulls adp data and saves to SQL server
#creates following table: adp
def adp_pull (years,agent,conn):
    logging.info("----------------------------------------adp_pull----------------------------------------")
    i = 1
    for year in years:
        if i>1:
            pause()

        logging.info(f"begin parsing year: {year}")
        request_url = f"https://api.myfantasyleague.com/{year}/export?TYPE=adp&JSON=1&{agent}&FCOUNT=12&&IS_KEEPER=N"
        req = requests.get(request_url)
        req_data = req.json()
        logging.info(f"connection results: {req}")
        
        adp = pd.json_normalize(req_data["adp"],record_path=["player"])

        adp = clean_adp(adp)
        
        adp["year"] = year
        
        adp.to_sql("adp", conn, if_exists="append")
        i =i+1

#cleans points allowed table
def clean_points_allowed(points_allowed):
    
    #convert datatype
    points_allowed = points_allowed.astype({"points":float})
    #rename columns
    points_allowed.rename(columns = {"name":"pos"},inplace=True)
    #convert to points/week
    points_allowed["points"] = (points_allowed["points"]/16).round(2)
    #calculate total points and make into df
    total_points = pd.DataFrame({
        "points":[points_allowed["points"].sum()],
        "pos":["ALL"]})
    #add total points
    points_allowed = pd.concat([points_allowed,total_points],ignore_index=True)

    return points_allowed

#pulls points allowed data and saves to SQL server
#creates following table: points_allowed
def points_allowed_pull(years,agent,conn,league_id):
    logging.info("----------------------------------------points_allowed_pull----------------------------------------")
    i = 1
    for year in years:
        if i>1:
            pause()

        
        logging.info(f"begin parsing year: {year}")
        request_url = f"https://www54.myfantasyleague.com/{year}/export?L={league_id}&TYPE=pointsAllowed&JSON=1&{agent}"
        req = requests.get(request_url)
        logging.info(f"connection results: {req}")
        req_data = req.json()
            
        teams = req_data['pointsAllowed']["team"]

        for team in teams:
            points_allowed = pd.json_normalize(team,record_path=["position"])

            points_allowed = clean_points_allowed(points_allowed)

            points_allowed["team"] = team["id"]

            points_allowed.to_sql("points_allowed", conn, if_exists="append")
        i = i+1

#cleans projected scores table
def clean_projected_scores(projected_scores):
    #delete rows with blank entries
    projected_scores = projected_scores.loc[~((projected_scores["score"]=="") | (projected_scores["id"]==""))]
    #convert datatypes
    projected_scores = projected_scores.astype({
    "score":float,
    "id":int
    })
    #rename columns
    projected_scores.rename(columns = {"score":"projected_scores"},inplace=True)
    return projected_scores

#pulls projected score data and saves to SQL server
#creates following table: projected_scores_pull
#very long pause due to numerous API requests
def projected_scores_pull(years,agent,conn,league_id):
    logging.info("----------------------------------------projected_scores_pull----------------------------------------")
    i = 1
    for year in years:
        if i>1:
            pause(300)
        
        logging.info(f"begin parsing year: {year}")
        weeks = list(range(1,19))
        
        for week in weeks:
            logging.info(f"parsing week: {week}")
            request_url = f"https://www54.myfantasyleague.com/{year}/export?L={league_id}&W={week}&TYPE=projectedScores&JSON=1&{agent}"
            req = requests.get(request_url)
            logging.info(f"connection results: {req}")
            req_data = req.json()

            projected_scores = pd.json_normalize(req_data["projectedScores"],record_path=["playerScore"])

            projected_scores = clean_projected_scores(projected_scores)

            short_pause()

            projected_scores.to_sql("projected_scores", conn, if_exists="append")


        i = i+1

#cleans league data
def clean_league_teams(league_teams):
    league_teams = league_teams[["icon","name","id","logo"]]
    league_teams = league_teams.astype({"id":int})
    return league_teams

#pulls league data and saves to SQL server, this will replace any other entry in server
#creates following table: league_teams
def league_teams_pull(years,agent,conn,league_id):
    logging.info("----------------------------------------league_teams_pull----------------------------------------")
    year = years[-1]
    request_url = f"https://www54.myfantasyleague.com/{year}/export?L={league_id}&TYPE=league&JSON=1&{agent}"
    req = requests.get(request_url)
    logging.info(f"connection results: {req}")
    req_data =req.json()
    league_teams = pd.json_normalize(req_data["league"]["franchises"],record_path = ["franchise"])

    league_teams = clean_league_teams(league_teams)

    league_teams.to_sql("league_teams", conn, if_exists="replace")

#constructs dataframe from scraped data
def df_construct(row):
    spread = row[6].string.split()[-1]
    spread = spread.replace("PK","0")
    fav_spread = float(spread)
    dog_spread = fav_spread*-1
    fav_result_spread = row[6].string.split()[0]


    over_under = float(row[9].string.split()[-1])

    score=row[5].string
    score = score.replace("(OT)","").strip()

    fav_score = int(score.split()[-1].split("-")[0])
    dog_score = int(score.split()[-1].split("-")[-1])
    fav_result = score.split()[0]



    favorite = pd.DataFrame({
        "day":[row[0].string],
        "date":[row[1].string],
        "time":[row[2].string],
        "team":[row[4].string],
        "opp":[row[8].string],
        "score":fav_score,
        "opp_score":dog_score,
        "result":fav_result,
        "spread":fav_spread,
        "result_spread":fav_result_spread,
        "over_under":over_under
        })

    dog = pd.DataFrame({
        "day":[row[0].string],
        "date":[row[1].string],
        "time":[row[2].string],
        "team":[row[8].string],
        "opp":[row[4].string],
        "score":dog_score,
        "opp_score":fav_score,
        "result":fav_result,
        "spread":dog_spread,
        "result_spread":fav_result_spread,
        "over_under":over_under
        })

    dog["result"].replace({"W":"L","L":"W"},inplace=True)
    dog["result_spread"].replace({"W":"L","L":"W"},inplace=True)

    spread = pd.concat([favorite,dog],ignore_index=True)

    return spread

#creates score prediction from scraped spreads
def score_preds(spreads):
    spreads["predicted_score"] = spreads["over_under"]/2 - spreads["spread"]/2
    spreads["opp_predicted_score"] = spreads["over_under"]/2 + spreads["spread"]/2
    return spreads

#fixes names in scraped data to match data from APIs
def team_name_fixer(df):
    
    #dictionairy to convert team names to match the rest of the server
    team_dict = {'New England Patriots':"NEP",
        'Kansas City Chiefs':"KCC",
        'Buffalo Bills':"BUF",
        'New York Jets':"NYJ",
        'Atlanta Falcons':"ATL",
        'Chicago Bears':"CHI",
        'Cincinnati Bengals':"CIN",
        'Baltimore Ravens':"BAL",
        'Pittsburgh Steelers':"PIT",
        'Cleveland Browns':"CLE",
        'Arizona Cardinals':"ARI",
        'Detroit Lions':"DET",
        'Houston Texans':"HOU",
        'Jacksonville Jaguars':"JAC",
        'Tennessee Titans':"TEN",
        'Oakland Raiders':"OAK",
        'Philadelphia Eagles':"PHI",
        'Washington Redskins':"WAS",
        'Los Angeles Rams':"LAR",
        'Indianapolis Colts':"IND",
        'Green Bay Packers':"GBP",
        'Seattle Seahawks':"SEA",
        'Carolina Panthers':"CAR",
        'San Francisco 49ers':"SFO",
        'Dallas Cowboys':"DAL",
        'New York Giants':"NYG",
        'Minnesota Vikings':"MIN",
        'New Orleans Saints':"NOS",
        'Denver Broncos':"DEN",
        'Los Angeles Chargers':"LAC",
        'Tampa Bay Buccaneers':"TBB",
        'Miami Dolphins':"MIA",
        'Las Vegas Raiders':"LVR",
        'Washington Football Team':"WAS"}

    df.replace(team_dict,inplace=True)

    return df

#scrapes website for spreads
#creates the following table: "spreads"
def spread_scraper(years,conn):
    logging.info("----------------------------------------spread_scraper----------------------------------------")
    for year in years:
        spreads = pd.DataFrame()
        logging.info(f"scraping year: {year}")
        #connect to year page
        BS_link = f"https://www.sportsoddshistory.com/nfl-game-season/?y={year}"
        sauce = requests.get(BS_link)
        soup = bs4.BeautifulSoup(sauce.text, 'html.parser')
        target = soup.find("h3", string=f"{year} Regular Season - Week 1")

        week_tables = target.find_next_siblings('table')
        #remove playoffs
        week_tables = week_tables[:-1]

        week = 1
        for week_table in week_tables:
            #find rows in week table
            rows = week_table.find_all("tr")
            #trim header off rows
            rows = rows[1:]
            for entry_row in rows:
                row = entry_row.find_all("td")
                spread = df_construct(row)
                spread["week"] = week
                spread["year"] = year
                spreads = pd.concat([spreads,spread],ignore_index=True)
            week = week+1
        spreads = score_preds(spreads)
        spreads.to_sql("spreads", conn, if_exists="append")

#Define class for entry widget
class GetEntry():

    def __init__(self, master):


        self.master=master
        self.master.title("Database Setup")
        self.agent=None
        self.league_id=None
        self.db_name=None
        self.years=None

        ## Set entries

        # insantiate entries
        self.agent_entry = tk.Entry(master)
        self.league_id_entry = tk.Entry(master)
        self.db_name_entry = tk.Entry(master)
        self.years_entry = tk.Entry(master)
        
        # building grid
        self.agent_entry.grid(row=0, column=1)
        self.league_id_entry.grid(row=1, column=1)
        self.db_name_entry.grid(row=2, column=1)
        self.years_entry.grid(row=3, column=1)


        # labels
        tk.Label(master, text="My Fantasy API Agent:",justify = tk.LEFT).grid(row=0)
        tk.Label(master, text="League ID:",justify = "left").grid(row=1)
        tk.Label(master, text="Database Name:",justify = "left").grid(row=2)
        tk.Label(master, text="Years to pull: \n (input as list *,*)",justify = "left").grid(row=3)


        tk.Button(master, 
                text='Go', 
                command=self.callback).grid(row=4, 
                                            column=0, 
                                            sticky=tk.W, 
                                            pady=4)

    def callback(self):
        """ get the contents of the Entries and exit the prompt"""
        self.agent=self.agent_entry.get()
        self.league_id=self.league_id_entry.get()
        self.db_name=self.db_name_entry.get()
        self.years=self.years_entry.get()
        self.master.destroy()


if __name__ == "__main__":
    main()

