# Fantasy Football

This project is a work in progress and is still being updated regularly as I build more ML models and implement more database features.

Summary
---
Collects data from numerous online sources; APIs and Web scraping, to analyze Fantasy Football analytics. Using this data, machine learning models are implemented to make predictions about individual player performance and draft pick value.

Data Wrangling
---

This project uses data from 2 main sources:
* API from [myfantasyleague.com](https://api.myfantasyleague.com/2022/api_info) for fantasy football data
* Web scraping from https://www.sportsoddshistory.com/ for historical scores, spreads and over/unders

This data is collected, cleaned, and saved to SQL server for analysis. To setup a similar database, you can use: Fantasy_Football_Server_Initialization_v*. This script will setup an SQLite server and populate it from the above sources. Please note: The API requests are spaced out in order to prevent being locked out by myfantasyleague, because of this the script will take ~30 minutes to run.

The list of tables generated by the script are as follows:

| Table Name | Description | Source |
| ------------- | ------------- | ------------- |
| weekly_players | Weekly results, broken down by players | https://api.myfantasyleague.com/2022/api_info |
| weekly_teams | Weekly results, broken down by teams | https://api.myfantasyleague.com/2022/api_info |
| weekly_matchups | Weekly results, broken down by matchups | https://api.myfantasyleague.com/2022/api_info |
| simple_players | Simple player information, by year | https://api.myfantasyleague.com/2022/api_info |
| adp | Average draft postion information, for each player, by year | https://api.myfantasyleague.com/2022/api_info |
| points_allowed | Average points allowed by team per position, per week | https://api.myfantasyleague.com/2022/api_info |
| projected_scores | My fantasy projected score for given player and given week | https://api.myfantasyleague.com/2022/api_info |
| league_teams | Information for teams in fantasy league | https://api.myfantasyleague.com/2022/api_info |
| spreads | Vegas spreads and results by year/week. 2 entries per matchup | https://www.sportsoddshistory.com |

* For a more in-depth explanation of tables and data, view "My_Fantasy_Data_Dictionary.xlsx" in the repository


Exploratory Analysis
---

My fantasy football league started in 2017. The league consists of 12 teams, with active rosters of 29 players. Each week, teams choose 9 starters that are any combination of the following player types: 1-2 QBs, 2-5 RBs, 2-5 WRs, and 1-4 TEs. The scoring is 0.5 pt. PPR, with the exception of TEs who get a full point. In the following sections I will use the term "starter" to refer to a player who was chosen by the fantasy team owner to start on a given week.

**Player Starts**

From 2017-2021 there have been 6966 player starts; 2519 WRs, 2028 RBs, 1448 QBs, and 971 TE's. These starts represent 466 unique players.

![image](https://user-images.githubusercontent.com/99829862/178121244-14dc91cf-6ba0-4263-92c3-1452561475f5.png)

**Player Scores**

It is possible to further break down player starts, by looking at the points scored, by position for every starter. This will tell us what is a "good" score for a certain position vs. a "bad" one. The following is a histogram of scores for every starter by position:

![image](https://user-images.githubusercontent.com/99829862/178121824-f0cfa86f-026c-4835-a53b-61279f1f64ad.png)

The reason we look at scores from starts only, is that we are interested in where a specific score will rank a player compared to other starters. Outscoring bench players or injured players does not tell us much about a player's performance.

The vertical green line is the 50th percentile (median) of starts. Any score over this threshold can be considered a good score, if a player reaches this score, there is a good chance they will be in the top 1/2 of starter scores for that week. The red line is the 90th percentile, this is an elite score, if a player reaches this score, there is a good chance they will be in the top 10% of starter scores for that week. In QBs, for example, this would be a top 2 performance.

**Team Scores**

Each week the fantasy team owners choose which players to start, and which players to bench. Football is a game with a lot of randomness, and choosing the best possible line-up is rarely done. This is demonstrated clearly by the distribution of weekly team scores vs. possible weekly team scores. Where possible weekly team score is the score that could have been achieved if the fantasy team owner had chosen the ideal line-up.

![image](https://user-images.githubusercontent.com/99829862/178123163-149bf757-e347-43cf-92af-ca58fac8b181.png)

| Item | Value | 
| ------------- | ------------- | 
| median weekly team score | 114.3 |
| median possible weekly team score | 140.0 |
| Avg(score - possible_score) | 24.3 |

As you can see from the above table, fantasy team owners are missing out, on average 24.3 points. That is more than enough to change the outcome of a matchup.

Player Score Regression Modelling
---

In order to choose the best lineup each week, we first need to better predict a players score for a given week. This is a regression problem. I attempted multiple models, on various features, but I found the best success with the following conditions:

* Model: Gradient Boosting Regressor
* Features:
  * player position
  * week
  * day of the week
  * time of game
  * NFL spread
  * predicted score of player's NFL team
  * average points allowed to player's position from opposing team
  * player ADP
  * player projections from myFantasy website
* Target: player scores

Using these conditions, I generated two similar models, one using squared error as the loss function, and one using absolute error. I think in later implementations of these models, there might be cases where one is preferable over the other. To train and evaluate these models, I used a standard 75%/25% train/test split. These are the accuracy scores using the test set of data:

| Model | R2 | MAE | MSE | RMSE |
| ------------- | ------------- | ------------- | ------------- | ------------- |
| GBR_MAE | 0.4464 | 4.25 | 37.97 | 6.16 |
| GBR_RMSE | 0.4682 | 4.45 | 36.48 | 6.04 |


Player Score Regression Model Evaluation
---

When it comes to predicting player score, not all errors are created equal. If a player out-scores a prediction it is a happy surprise, if the player under-scores a prediction it's a sad result. By comparing predicted scores vs. actual scores on the test set of data (by position) I get the following:

![image](https://user-images.githubusercontent.com/99829862/178125441-99bcbccf-5899-4937-986a-2bf82ecc7580.png)

Any score above the red line is one of those happy surprises I mentioned above, and anything below could cost you the game.

**SO... Who Should I Start?!**

At this point, I think it's important to consider the purpose of this model: to decide which players to start. The true test of whether or not this model is useful, is its ability to predict a player's chance of producing a "good" starting score. Lets explore this using the score threshold defined above: a "good" score is defined as: a score >= the median score for starters at that position. Lets see what that looks like on our score vs. prediction graphs:

![image](https://user-images.githubusercontent.com/99829862/178125864-e816fddc-9352-4cb9-b981-90dec9aed9e8.png)

When viewing the scores vs. predictions this way, we can identify 4 quadrants:

![image](https://user-images.githubusercontent.com/99829862/178126052-384006d4-b2fc-4cad-9aad-dd1037709185.png)

* Q1: prediction = "bad" starting score, result = "good" starting score (false negative)
* Q2: prediction = "good" starting score, result = "good" starting score (true positive)
* Q3: prediction = "bad" starting score, result = "bad" starting score (true negative)
* Q4:  prediction = "good" starting score, result = "bad" starting score (false positive)

This is starting to look like a classification problem. But before we build another model, lets convert our predicted scores to these binary good_score/bad_score categories, and evaluate.

Model Metrics:

![image](https://user-images.githubusercontent.com/99829862/178128384-212d2dee-2b30-41ee-a6eb-8a82907c7cc5.png)

While the accuracy is just OK, at 64%. The most notable metric is the recall for the "bad_score" outcome. The model achieved 80%, this means that this model can tell you who NOT to start with 80% accuracy.

The next step is to build a new model, treating it as a classification problem from the beginning and see if we can improve our results.

Player Score Classification Modelling
---

Coming Soon



