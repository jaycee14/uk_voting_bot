import json
import os
import re
from collections import defaultdict

from fuzzywuzzy import process
from google.cloud import storage

NO_ISSUE_FOUND = 1
MP_NOT_FOUND = 2
PROJECT_BUCKET_REF = 'MP_BUCKET_NAME'
split_characters = re.compile(r'[^a-zA-Z0-9 ]')


#############################################################################
#################  I/O Functions ############################################
#############################################################################

def get_master_issue_json_from_cloud(fname='master_issues_list.json') -> dict:
    # abstraction layer to separate from cloud provider

    return get_file_from_gcp_bucket(fname)
    # return get_file_from_gcp_bucket_test(fname)


def get_voting_data_from_cloud(fname) -> dict:
    # abstraction layer to separate from cloud provider

    return get_file_from_gcp_bucket(fname)
    # return get_file_from_gcp_bucket_test(fname)


def get_file_from_gcp_bucket(filename) -> dict:
    bucket_name = os.getenv(PROJECT_BUCKET_REF)

    try:
        # Instantiate a Google Cloud Storage client and specify required bucket and file
        storage_client = storage.Client()
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(filename)

        # Download the contents of the blob as a string and then parse it using json.loads() method
        data = json.loads(blob.download_as_string(client=None))

        return data
    except:
        return None


def get_since_id_from_cloud(filename: str = 'since_id.json'):
    data = get_file_from_gcp_bucket(filename)
    # log_data = get_file_from_gcp_bucket_test(filename)

    if data is None:
        return None
    else:
        return data['since_id']


def put_since_id_to_cloud(since_id: int, filename: str = 'since_id.json'):
    data = {'since_id': since_id}
    put_data_to_gcp_bucket_file(data, filename)
    # put_data_to_gcp_bucket_file_test(data, filename)


def put_log_data_to_cloud(data: dict, filename: str = 'mp_voting_log.json'):
    put_data_to_gcp_bucket_file(data, filename)
    # put_data_to_gcp_bucket_file_test(data, filename)


def get_log_data_from_cloud(filename: str = 'mp_voting_log.json'):
    log_data = get_file_from_gcp_bucket(filename)
    # log_data = get_file_from_gcp_bucket_test(filename)

    if log_data is None:
        return []
    else:
        return log_data


def put_data_to_gcp_bucket_file(data: dict, filename: str):
    bucket_name = os.getenv(PROJECT_BUCKET_REF)

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)

    contents = json.dumps(data)

    blob.upload_from_string(contents)


def put_data_to_gcp_bucket_file_test(data: dict, filename: str):
    with open(filename, 'w') as f:
        json.dump(data, f)


def get_file_from_gcp_bucket_test(filename) -> dict:
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        return None

    return data


#############################################################################
#################  Process Functions ########################################
#############################################################################

def prepare_master_issues_json(master_issues: dict):
    if master_issues is None:
        return None, None, None

    master_issue_dict = {}
    all_issues = []
    issues_filenames = {}
    for issue in master_issues:
        sub = issue['subject']
        issues_filenames[sub] = issue['filename']
        for kw in issue['keywords']:
            master_issue_dict[kw] = sub
            all_issues.append(kw)

    return master_issue_dict, all_issues, issues_filenames


def clean_tweet_of_users(tweet_text: str, user_list: list) -> str:
    return_str = tweet_text
    for user in user_list:
        return_str = return_str.replace('@' + user['screen_name'], '')

    return return_str.strip()


def filter_tweets(twitter_objects, all_issues_list, master_issues_dict):
    prepare_responses = defaultdict(list)
    max_id=1

    for obj in twitter_objects:

        if obj.id > max_id:
            max_id = obj.id

        # clean tweets
        message = clean_tweet_of_users(obj.full_text,
                                       obj.entities['user_mentions'])

        find_non_char = split_characters.findall(message)

        if len(find_non_char) >= 1:

            first_half, second_half = message.split(find_non_char[0])  # find first non text

            issue, mp_name = find_issue(all_issues_list, master_issues_dict, first_half, second_half)

            if issue != NO_ISSUE_FOUND:

                prepare_responses[issue].append({'tweet_data': obj, 'mp_name': mp_name})

            else:
                print('Not yet covered')

        else:
            print('Incorrect format')

    return prepare_responses, max_id


def prepare_responses(prepared_responses, issues_filenames):
    output_objects = []

    for subject, tweet_obj_list in prepared_responses.items():

        # load the correct file
        fname = issues_filenames[subject]

        vote_data_all = get_voting_data_from_cloud(fname)

        vote_data = vote_data_all['vote_data']
        vote_url = vote_data_all['vote_url']

        mp_name_list = vote_data.keys()

        for tweet_obj in tweet_obj_list:

            mp_name = tweet_obj['mp_name']

            original_tweet = tweet_obj['tweet_data']

            # look up voting against issues
            mp_checked_name = find_mp(mp_name, mp_name_list)

            if mp_checked_name != MP_NOT_FOUND:

                if original_tweet.in_reply_to_status_id is None:
                    reply_name = original_tweet.author.screen_name
                else:
                    reply_name = original_tweet.in_reply_to_screen_name

                response_tweet = format_response(vote_data, mp_checked_name, vote_url, reply_name)
                # print(response_tweet)
                tweet_obj['response_text'] = response_tweet
                tweet_obj['reply_id_str'] = original_tweet.id_str

                output_objects.append(tweet_obj)

            else:
                print('MP not found')

    return output_objects


def find_issue(keywords, master_dict, first_half, second_half, threshold=80):
    result = run_check(keywords, second_half)

    if result:
        subject = master_dict[result]
        return subject, first_half

    result = run_check(keywords, first_half)

    if result:
        subject = master_dict[result]
        return subject, second_half

    return NO_ISSUE_FOUND, None


def run_check(keywords, message, limit=1, threshold=80):
    comparison = process.extract(message, keywords, limit=limit)

    if len(comparison) < 1:
        return None

    if comparison[0][1] < threshold:
        return None

    return comparison[0][0]


def find_mp(proposed_name, name_list, limit=1, threshold=80):
    result = process.extract(proposed_name, name_list, limit=limit)

    if len(result) >= 1:

        match_name, score = result[0]
        if score > threshold:
            return match_name

    return MP_NOT_FOUND


def format_response(vote_data, name, vote_url, reply_screen_name):
    output_str = '@' + reply_screen_name

    if name in vote_data:

        vote_data_mp = vote_data[name]

        member = vote_data_mp['Member']
        const = vote_data_mp['Constituency']
        party = vote_data_mp['Party']
        vote = vote_data_mp['Vote']

        if vote in ['No', 'Teller - Noes']:
            output_str += f' {member} ({party} - {const}) voted against this measure. {vote_url}'
        elif vote in ['Aye', 'Teller - Ayes']:
            output_str += f' {member} ({party} - {const}) voted for this measure. {vote_url}'
        elif vote == 'No Vote Recorded':
            output_str += f' No voting record was found for {member} ({party} - {const}) on this measure. {vote_url}'
    else:
        output_str += ' No record found'

    return output_str
