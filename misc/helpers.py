import bs4
import requests
from PIL import Image

total_tagged = 0
total_untagged = 0

def resize_image(local_image_path):
    with Image.open(local_image_path) as image:
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

def statistics(tagged=0, untagged=0):
    global total_tagged
    global total_untagged

    total_tagged   += tagged
    total_untagged += untagged

    return total_tagged, total_untagged

def audit_rating(*ratings):
    """
    Return the highest among the scraped ratings
    Returns 'safe' if ratings is an empty list
    """

    verdict = 'safe'
    weight = {
        'unsafe' : 2,
        'sketchy': 1,
        'safe'   : 0
    }
    for r in ratings:
        if not r:
            continue
        if weight[r] > weight[verdict]:
            verdict = r
    return verdict

def remove_tag_whitespace(tags_whitespace):
    """
    Self descriptive
    Szurubooru does not allow whitespaces in tagnames

    Arguments:
        tags: list of tags possibly with whitespaces

    Returns:
        tags_: list of tags with underscores
    """
    tags_underscore = []
    for tw in tags_whitespace:
        tu = tw.replace(' ', '_')
        tags_underscore.append(tu)

    return tags_underscore

def collect_tags(*list_tags):
    """
    Collect tags and remove duplicates
    Retuns an empty list if tags is an empty list

    Arguments:
        list_tags: A list of lists of tags

    Returns:
        tags_collected: self descriptive
            duplicates are removed
    """

    tags_collected = []
    for lt in list_tags:
        tu = remove_tag_whitespace(lt)
        tags_collected.extend(tu)

    for tc in tags_collected:
        tc.replace(' ', '_')

    # remove duplicates
    tags_collected = list(set(tags_collected))
    return tags_collected

def collect_sources(*sources):
    """
    Collect sources in a single string separated by newline characters
    Returns an empty string if sources is an empty list

    Arguments:
        sources: A list of source URL strings

    Returns:
        source_collected: Collection of sources in a string
            separated by newline character
    """

    source_valid = []
    # remove empty sources
    for s in sources:
        if not s:
            continue
        source_valid.append(s)

    # remove duplicates
    source_valid = list(set(source_valid))

    delimiter = '\n'
    source_collected = delimiter.join(source_valid)
    return source_collected
