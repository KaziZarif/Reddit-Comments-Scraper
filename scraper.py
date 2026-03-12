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
SEARCH_PHRASE = config['search_phrase']
BLACKLIST = config['blacklist']

def scrape_comments():
    url = "https://api.pullpush.io/reddit/search/comment/"
    all_results = []
    current_before = int(time.time())

    print(f"Starting scraper....")

    while len(all_results) < config['target_count']:
        params = {
            'q': SEARCH_PHRASE,
            'size': 100,
            'before': current_before,
            'sort': 'desc'
        }
    
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                print(f"API Error: {response.status_code}. Retrying in 5s...")
                time.sleep(5)
                continue

            data = response.json().get('data', [])
            if not data:
                print("No more results found.")
                break
            
            filtered_batch = [
                {
                    "comment_id": c['id'],
                    "body": c['body'],
                    "post_id": c['link_id'],
                    "subreddit": c['subreddit'],
                    "permalink": f"https://reddit.com{c['permalink']}"
                }
                for c in data
                if c['subreddit'].lower() not in BLACKLIST
            ]
            
            all_results.extend(filtered_batch)
            current_before = data[-1]['created_utc']
            print(f"Collected {len(all_results)} comments... (Last date: {datetime.fromtimestamp(current_before)})")
            time.sleep(1)
        
        except Exception as e:
            print(f"Connection error: {e}. Sleeping 10s...")
            time.sleep(10)

    unique_post_ids = list(set([c['post_id'] for c in all_results]))
    title_map =  {}
    for i in range(0, len(unique_post_ids), 100):
        batch = unique_post_ids[i: i + 100]
        titles = fetch_post_titles(batch)
        title_map.update(titles)

    for comment in all_results:
        short_id = comment['post_id'].replace("t3_", "")
        title = title_map.get(short_id, "Title Not Found")

        if not title or title == "Title Not Found":
            comment['post_title'] = extract_title_from_permalink(comment['permalink'])
        else:
            comment['post_title'] = title


    with open("raw_comments.json", "w") as f:
        json.dump(all_results, f, indent=4)
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
    