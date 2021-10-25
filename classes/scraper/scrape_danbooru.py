import requests
import bs4
import re

def scrape_danbooru(danbooru_image_url):
    # set default values
    tags = []
    source = ''
    rating = 'unsafe'

    # scrape tags from danbooru_image_url
    response = requests.get(danbooru_image_url, timeout=20)
    html = bs4.BeautifulSoup(response.text, 'html.parser')

    # scrape tags
    tag_list = html.find('section', {'id' : 'tag-list'})
    tag_infos = tag_list.find_all('li', {'class' : re.compile('tag-type')})
    for ti in tag_infos:
        tag_href = ti.find('a', {'class' : 'search-tag'})
        tag = tag_href.text
        tags.append(tag)

    # scrape rating
    post_info = html.find('section', {'id' : 'post-information'})
    li_rating = post_info.find('li', {'id' : 'post-info-rating'})
    rating_raw = li_rating.text
    # trim unnecessary characters
    rating_raw = rating_raw.replace('Rating: ', '')
    # convert rating Gelbooru -> Szurubooru
    if rating_raw == 'Explicit':
        rating = 'unsafe'
    elif rating_raw == 'Safe':
        rating = 'safe'
    elif rating_raw == 'Questionable':
        rating = 'sketchy'

    # scrape source
    try:
        li_source = post_info.find('li', {'id' : 'post-info-source'})
        a_source = li_source.find('a', href=True)
        source = a_source[0]['href']
    except:
        source = danbooru_image_url

    return tags, source, rating
