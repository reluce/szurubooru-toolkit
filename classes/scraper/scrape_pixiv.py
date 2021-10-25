import requests
import bs4
import re

def scrape_pixiv(result):
    # set default values
    tags = []
    source = ''
    rating = 'unsafe'

    # scrape tags from result.url
    response = requests.get(result.url, timeout=20)
    html = bs4.BeautifulSoup(response.text, 'html.parser')
