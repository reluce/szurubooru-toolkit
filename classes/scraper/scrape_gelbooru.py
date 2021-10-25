import requests
import bs4
import re

def scrape_gelbooru(gelbooru_image_url):
    # set default values
    tags = []
    source = ''
    rating = 'unsafe'

    # scrape tags from gelbooru_image_url
    response = requests.get(gelbooru_image_url, timeout=20)
    html = bs4.BeautifulSoup(response.text, 'html.parser')
    sidebar = html.find('section', {'class' : 'aside'})
    # remove <br/> tags that breaks beautifulsoup4
    for linebreak in sidebar.find_all('br'):
        linebreak.extract()

    # scrape tags
    tag_infos = sidebar.find_all('li', {'class' : re.compile('tag-type')})
    for ti in tag_infos:
        tag_href = ti.find_all('a')
        tag = tag_href[1].text
        tags.append(tag)

    # scrape rating
    li_rating = sidebar.find('li', text=re.compile('Rating'))
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
    source = gelbooru_image_url

    return tags, source, rating
