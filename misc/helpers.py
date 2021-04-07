import bs4
import requests
from PIL import Image

def resize_image(local_image_path):
    image = Image.open(local_image_path)
    image.thumbnail((1000, 1000))
    image.save(local_image_path)

def convert_rating(rating):
    """
    Map found rating to szuru rating
    """

    switch = {
        'Safe': 'safe',
        's': 'safe',
        'Questionable': 'sketchy',
        'q': 'sketchy',
        'Explicit': 'unsafe',
        'e': 'unsafe'
    }

    return switch.get(rating)

def get_metadata_sankaku(sankaku_url):
    response    = requests.get(sankaku_url)
    result_page = bs4.BeautifulSoup(response.text, 'html.parser')

    rating_raw = str(result_page.select('#stats li'))
    rating_mixed = rating_raw.partition('Rating: ')[2]
    rating_sankaku = rating_mixed.replace('</li>]', '')
    rating = convert_rating(rating_sankaku)

    tags_raw = str(result_page.title.string)
    tags_mixed = tags_raw.replace(' | Sankaku Channel', '')
    tags_stirred = tags_mixed.replace(' ', '_')
    tags_fried = tags_stirred.replace(',_', ' ')

    tags = tags_fried.split()

    return tags, rating

def statistics(tagged, untagged):
    total_tagged   += tagged
    total_untagged += untagged

    return total_tagged, total_untagged
