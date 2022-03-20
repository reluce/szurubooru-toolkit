import re

from szuru_toolkit.utils import convert_rating

import bs4
import requests


def scrape_sankaku(sankaku_image_url):
    '''
    Scrape tags, source, rating from Sankaku Complex

    Arguments:
        result: saucenao search result that is indexed as Sankaku
            expecting result.url and result.source_url

    Returns:
        tags: self descriptive
        source: URL of the image source
        rating: either 'unsafe', 'safe' or 'sketchy'
    '''
    # set default values
    tags = []
    source = ''
    rating = 'unsafe'

    # scrape tags from sankaku_image_url
    response = requests.get(sankaku_image_url, timeout=20)
    html = bs4.BeautifulSoup(response.text, 'html.parser')

    # scrape tags
    tag_sidebar = html.find('ul', {'id': 'tag-sidebar'})
    tag_infos = tag_sidebar.find_all('li', {'class': re.compile('tag-type')})
    for ti in tag_infos:
        tag_href = ti.find('a', {'itemprop': 'keywords'})
        tag = tag_href.text
        tags.append(tag)

    # scrape rating
    stats = html.find('div', {'id': 'stats'})
    li_rating = stats.find('li', text=re.compile('Rating'))
    rating_raw = li_rating.text
    # trim unnecessary characters
    rating_raw = rating_raw.replace('Rating: ', '')
    # convert rating Sankaku -> Szurubooru
    rating = convert_rating(rating_raw)

    # scrape source
    source = sankaku_image_url

    return tags, source, rating
