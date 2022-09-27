
import pandas as pd
import numpy as np
import math
import json
from sqlalchemy import create_engine, inspect
from flask import Flask, make_response, request, redirect, url_for, abort, session, jsonify

app = Flask(__name__)

#creating custom dtype for start type ordering
from pandas.api.types import CategoricalDtype
start_type_data = CategoricalDtype(["DNP", "Trash Start", "Bad Start", "Good Start", "Elite Start"], ordered=True)

#creating start cleaner
def start_cleaner(starts_df):

        #filter to specific pick group and groups by start type
        starts = starts_df.groupby(by=["start_type"],as_index=False).count()

        #deletes eronous columns
        starts = starts[["start_type","week"]]
        #renames column
        starts = starts.rename(columns = {"week":"count"})

        #calculating # of games since joining league
        total_starts = starts["count"].sum()

        #calculating start type %
        starts["%"] = (starts["count"]/total_starts).round(2)*100

        #Sorting by start type
        starts["start_type"] = starts["start_type"].astype(start_type_data)
        starts.sort_values(["start_type"], ascending=False, inplace=True)

        return starts

@app.route("/player/<id>")
def player_eval(id):
        # create sqlite engine for fantasy_league db
        engine = create_engine("sqlite:///fantasy_football_data.db", echo=True)
        #create connection to the engine
        conn = engine.connect()
        points_sql = f"""SELECT *
                FROM player_points
                WHERE id = {id}
                """

        starts_sql = f"""SELECT *
                FROM player_start_numbers
                WHERE id = {id}
                """

        points_df = pd.read_sql_query(points_sql, engine)
        starts_df = pd.read_sql_query(starts_sql, engine)
        
        starts_df = start_cleaner(starts_df)

        points_table = json.loads(points_df.to_json(orient="records"))
        starts_table = json.loads(starts_df.to_json(orient="records"))
        
        combined_table = {"points":points_table,"starts":starts_table}
        return combined_table

@app.route("/draft_pick/<pick>")
def pick_eval(pick):
        
        # create sqlite engine for fantasy_league db
        engine = create_engine("sqlite:///fantasy_football_data.db", echo=True)
        #create connection to the engine
        conn = engine.connect()
        
        #convert pick # to pick group
        pick_group = math.floor(int(pick)/4)+1
        
        
        points_sql = f"""SELECT *
                FROM draft_pick_points
                WHERE pick_group = {pick_group}
                """

        starts_sql = f"""SELECT *
                FROM draft_pick_start_numbers
                WHERE pick_group = {pick_group}
                """

        points_df = pd.read_sql_query(points_sql, engine)
        starts_df = pd.read_sql_query(starts_sql, engine)
        
        starts_df = start_cleaner(starts_df)

        points_table = json.loads(points_df.to_json(orient="records"))
        starts_table = json.loads(starts_df.to_json(orient="records"))
        
        combined_table = {"points":points_table,"starts":starts_table}
        return combined_table
