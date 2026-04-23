import requests
import time
import json
import os
import sys
import re
from datetime import datetime 

def load_config():
    if not os.path.exists('config.json'):
        print("Error: config.json not found!")
        print("Please copy config.json.example to config.json and fill it out.")
        sys.exit(1)
    with open('config.json', 'r') as f:
        return json.load(f)
    
config = load_config()
SEARCH_PHRASES = config.get('search_phrases', [config.get('search_phrase')])
BLACKLIST = config.get('blacklist', [])

def scrape_comments():
    url = "https://api.pullpush.io/reddit/search/comment/"
    all_results = []
    existing_ids = set()
    # current_before = int(time.time())

    cursors = {phrase: int(time.time()) for phrase in SEARCH_PHRASES}

    print(f"Starting Search...")

    # phrases = config.get('search_phrases', [config.get('search_phrase')])
    while len(all_results) < config['target_count']:
        pot = []
        found_this_round = False 

        for phrase in SEARCH_PHRASES:
            params = {
                'q': phrase,
                'size': 50,
                'before': cursors[phrase],
                'sort': 'desc'
            }
        
            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code != 200:
                    continue

                data = response.json().get('data', [])
                if not data:
                    continue

                found_this_round = True 
                cursors[phrase] = int(data[-1]['created_utc']) -1

                for c in data:
                    if c['subreddit'].lower() not in BLACKLIST:
                        pot.append(c)

            except Exception as e:
                print(f"Error fetching phrase '{phrase}': {e}")

        if not found_this_round:
            print("No more results found for any search phrase.")
            break

        pot.sort(key=lambda x: int(x['created_utc']), reverse=True)

        for c in pot:
            if c['id'] not in existing_ids:
                if len(all_results) < config['target_count']:
                    all_results.append({
                        "comment_id": c['id'],
                        "body": c['body'],
                        "post_id": c['link_id'],
                        "subreddit": c['subreddit'],
                        "created_utc": int(c['created_utc']),
                        "permalink": f"https://reddit.com{c.get('permalink', '')}"
                    })
                    existing_ids.add(c['id'])
                else:
                    break
        
        last_date = datetime.fromtimestamp(all_results[-1]['created_utc'])
        print(f"Collected {len(all_results)} total... (Current date: {last_date})")

        time.sleep(1)

    
    print("Fetching post titles...")
    unique_post_ids = list(set([c['post_id'] for c in all_results]))
    title_map = {}
    for i in range(0, len(unique_post_ids), 100):
        batch = unique_post_ids[i: i + 100]
        titles = fetch_post_titles(batch)
        title_map.update(titles)

    for comment in all_results:
        short_id = comment['post_id'].replace("t3_", "")
        title = title_map.get(short_id)
        if not title or title == "Title Not Found":
            comment['post_title'] = extract_title_from_permalink(comment['permalink'])
        else:
            comment['post_title'] = title 
    
    with open("raw_comments.json", "w", encoding='utf-8') as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)
    print(f"Data saved to raw_comments.json")


def extract_title_from_permalink(permalink):
    match = re.search(r'/comments/[^/]+/([^/]+)/', permalink)
    if match:
        clean_title = match.group(1).replace('_', ' ').replace('-', ' ')
        return clean_title
    return "Title Not Found"

def fetch_post_titles(post_ids):
    short_ids = ",".join([pid.replace("t3_", "") for pid in post_ids])
    url = f"https://api.pullpush.io/reddit/search/submission/?ids={short_ids}"
    
    try:
        response = requests.get(url, timeout=10)
        title_map = {}
        
        if response.status_code == 200:
            submissions = response.json().get('data', [])
            title_map = {s['id']: s['title'] for s in submissions}
        
        for pid in post_ids:
            sid = pid.replace("t3_", "")
            if sid not in title_map:
                fallback_url = f"https://api.pullpush.io/reddit/search/submission/?q={sid}"
                fallback_response = requests.get(fallback_url, timeout=5)
                if fallback_response.status_code == 200:
                    fallback_data = fallback_response.json().get('data', [])
                    if fallback_data:
                        title_map[sid] = fallback_data[0]['title']

        return title_map
    except Exception as e:
        print(f"Failed to fetch titles: {e}")
    return {}

if __name__ == "__main__":
    scrape_comments()
    