import os
from datetime import datetime

import tweepy
from flask import Flask, jsonify

from config import API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET
from voting_bot_utils import filter_tweets, prepare_responses, get_master_issue_json_from_cloud, \
    prepare_master_issues_json, get_since_id_from_cloud, put_since_id_to_cloud
from voting_bot_utils import put_log_data_to_cloud, get_log_data_from_cloud

DEBUG = False

app = Flask(__name__)

def bot_process():
    log = {}
    log['Datetime'] = datetime.now().isoformat()

    auth = tweepy.OAuth1UserHandler(
        API_KEY, API_SECRET,
        ACCESS_TOKEN, ACCESS_SECRET
    )
    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        print("Authentication Successful")
        log['Twitter auth success'] = True
    except:
        print("Authentication Error")
        log['Twitter auth success'] = False

    since_id = get_since_id_from_cloud()

    mentions = api.mentions_timeline(tweet_mode='extended', trim_user=False, count=100, since_id=since_id)
    log['Mentions'] = len(mentions)

    if len(mentions) > 0:

        master_issues = get_master_issue_json_from_cloud()

        if master_issues is None:
            log['master issues error'] = True
        else:
            master_issue_dict, all_issues, issues_filenames = prepare_master_issues_json(master_issues)

            filtered_tweets, max_id = filter_tweets(mentions, all_issues, master_issue_dict)
            log['Subjects detected'] = len(filtered_tweets.keys())

            # To do - respond to unrecognised subjects

            prepared_tweets = prepare_responses(filtered_tweets, issues_filenames)
            log['Prepared tweets'] = len(prepared_tweets)

            for prepared_tweet in prepared_tweets:

                if prepared_tweet['tweet_data'].id > max_id:
                    max_id = prepared_tweet['tweet_data'].id

                if DEBUG:
                    print(prepared_tweet['response_text'])
                else:
                    api.update_status(status=prepared_tweet['response_text'],
                                      in_reply_to_status_id=prepared_tweet['reply_id_str'])
            log['New Max ID'] = max_id
            put_since_id_to_cloud(since_id=max_id)

    log_data = get_log_data_from_cloud()
    log_data.append(log)
    put_log_data_to_cloud(log_data)

    return log

@app.route("/")
def run_process():
    data = bot_process()
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))