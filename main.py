from json.decoder import JSONDecodeError
import requests
import json
import time
import sys

class RateLimitError(Exception):
    def __init__(self):
        super().__init__()

def rate_limit(func):
    def wrapper(*args, **kwargs):
        while True:
            try:
                return func(*args, **kwargs)
            #sometimes anilist sends an actual ratelimiterror, sometimes it sends gibberish non-json
            except (RateLimitError, JSONDecodeError):
                print("Rate limit exceeded. Sleeping for 60 seconds")
                time.sleep(60)
    return wrapper

def checkerrors(response):
    response = json.loads(response.text.encode('utf8'))
    if "errors" in response.keys():
        if response["errors"][0]["status"] == 429:
            raise RateLimitError
    return response

#get anime list for given user ID as a list of {anime_id:score} dicts
@rate_limit
def get_anime_list(id,page=1):
    query = '''
        query ($id: Int!,$page:Int) {
      Page(page: $page, perPage: 100) {
      pageInfo {
        total
        perPage
      }
      mediaList(userId:$id) {
        media {
	     title {
	       romaji
	     }
	   }
        score(format:POINT_100)
      }
    }
    }
    '''
    url = 'https://graphql.anilist.co'
    variables = {
              "page": page,
              "id": id
        }
    response = checkerrors(requests.post(url, json={'query': query, 'variables': variables}))
    anime_list = [{x["media"]["title"]["romaji"]:x["score"]} for x in response["data"]["Page"]["mediaList"]]
    if len(anime_list) > 0:
        anime_list += get_anime_list(id,page+1)
    return anime_list

#get list of followers or followees for given user ID
@rate_limit
def get_following_list(id,is_followers,page=1):
    query = '''
        query ($id: Int!,$page:Int) {
          Page(page: $page, perPage: 50) {
          pageInfo {
            total
            perPage
          }
          following(userId:$id) {
            id
          }
        }
        }
        '''
    if is_followers:
        query = query.replace("following","followers")
    url = 'https://graphql.anilist.co'
    variables = {
              "page": page,
              "id": id
        }
    response = checkerrors(requests.post(url, json={'query': query, 'variables': variables}))
    if is_followers:
        following_list = [x["id"] for x in response["data"]["Page"]["followers"]]
    else:
        following_list = [x["id"] for x in response["data"]["Page"]["following"]]
    if len(following_list) > 0:
        following_list += get_following_list(id,is_followers,page+1)
    return following_list

#get user ID for a given username
@rate_limit
def get_user_id(username):
    query = '''
        query ($username: String) {
            User(name:$username) {
                id
            }
        }
        '''
    variables = {
            'username': username
        }
    url = 'https://graphql.anilist.co'
    response = checkerrors(requests.post(url, json={'query': query, 'variables': variables}))
    if not response["data"]["User"]:
        raise Exception("User not found. Please check your spelling and ensure user profile is public")
    return response["data"]["User"]["id"]

def construct_ratings(lst):
    anime_ids, scores, counters = [],[],[]
    for entry in lst:
        id,score = next(iter(entry)),next(iter(entry.values()))
        if score == 0:
            continue
        if id in anime_ids:
            idx = anime_ids.index(id)
            scores[idx] += score
            counters[idx] += 1
        else:
            anime_ids.append(id)
            #normalisation to prevent a 10/10 with 1 sample size dominating list
            scores.append(score+50)
            counters.append(2)
    average_scores = [round(x/y,2) for x,y in zip(scores,counters)]
    return sorted(list(zip(anime_ids,average_scores)),key=lambda x: x[1],reverse=True)

def pretty_print(out):
    print("Score | Anime")
    for elem in out:
        print(f"  {elem[1]}  | {elem[0]}")
    return

if __name__ == "__main__":
    id = get_user_id(sys.argv[1])
    #change that boolean argument to False and it'll compute for people who follow you (instead of people you follow)
    following_list = [n for l in [get_anime_list(x) for x in get_following_list(id,True)] for n in l]
    processed_following_list = construct_ratings(following_list)
    pretty_print(processed_following_list)
