import requests
import time
import json
import os
from datetime import datetime 

def scrape_comments():
    url = "https://api.pullpush.io/reddit/search/comment/"
    all_results = []
    current_before = int(time.time())

    print(f"Starting scraper....")