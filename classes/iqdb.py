import os
import requests
import bs4
import re
import urllib
from misc.helpers import resize_image, convert_rating

class IQDB:
    def __init__(self):
        self.base_url          = 'https://iqdb.org/'
        self.base_url_download = self.base_url + '?url='
        self.results           = False

    def get_result(self, post, booru_offline, local_temp_path):
        """
        If our booru is offline, upload the image to iqdb and return the result html page.
        Otherwise, let iqdb download the image from our szuru instance.
        """

        if(booru_offline == True):
            # Download temporary image
            filename = post.image_url.split('/')[-1]
            local_file_path = urllib.request.urlretrieve(post.image_url, local_temp_path + filename)[0]

            # Resize image if it's too big. IQDB limit is 8192KB or 7500x7500px.
            # Resize images bigger than 3MB to reduce stress on iqdb.
            image_size = os.path.getsize(local_file_path)

            if image_size > 3000000:
                resize_image(local_file_path)

            # Upload it to IQDB
            files    = {'file': open(local_file_path, 'rb')}
            response = requests.post(self.base_url, files=files)

            # Remove temporary image
            if os.path.exists(local_file_path):
                os.remove(local_file_path)
        else:
            response = requests.get(self.base_url_download + post.image_url, timeout=20)

        return(bs4.BeautifulSoup(response.text, 'html.parser'))

    def get_tags(self, result_page, booru):
        """
        Get tags from the preferred booru. If preferred booru yields no result, try fallback booru.
        If fallback booru also yields no result, call get_tags_best_match().
        """

        if result_page.find_all(text='No relevant matches'):
            self.results = False
            tags = ['tagme']
        else:
            self.results = True
            self.elems = result_page.select(f"#pages a[href*={booru}] > img")

            if(booru == 'sankaku'):
                tags = self.elems[0].get('title').split()[3:]
            else:
                tags = self.elems[0].get('title').split()[5:]

        return(tags)

    def get_tags_best_match(self, result_page, source):
        """
        If preferred and fallback booru yielded no results, try for best match.
        Zerochan meta data differ a bit from the others, so we have to call get_source() first
        and supply the source in order to differentiate.
        """

        self.elems = result_page.select('#pages > div:nth-child(2) > table:nth-child(1) > tr:nth-child(2) > td > a > img')

        if 'zerochan' in source:
            tags = self.elems[0].get('title').split(', ')[3:]

            for i in range(len(tags)):
                tags[i] = tags[i].lower()
                tags[i] = tags[i].replace(' ', '_')
        else:
            tags = self.elems[0].get('title').split()[5:]

        return(tags)

    def get_source(self, result_page, booru = None):
        """
        Get source from the result page. Searches for href.
        Search link for preferred of fallback booru.
        The else part gets executed from get_tags_best_match().
        """

        if booru:
            source_raw = str(result_page.select(f"#pages a[href*={booru}]"))
            source_mixed = source_raw.partition('href="//')[2]
        else:
            source_raw = str(result_page.select("#pages > div:nth-child(2) > table:nth-child(1) > tr:nth-child(2) > td > a"))
            source_mixed = source_raw.partition('href="')[2]

        source_stirred = re.sub(r'"><.*', '', source_mixed)
        source = 'https://' + source_stirred

        return(source)

    def get_rating(self):
        """
        Get rating, it's the eigth character - Rating: {s,q,e}
        Convert those ratings to szuru format
        """

        rating_raw = self.elems[0].get('title')[8]
        rating = convert_rating(rating_raw)

        return(rating)
