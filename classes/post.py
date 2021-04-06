class Post:
    def __init__(self, id=None, image_url=None, version=None):
        self.id            = id
        self.version       = version
        self.image_url     = image_url
        self.image         = None
        self.image_token   = None
        self.tags          = []
        self.rating        = 'unsafe'
        self.source        = 'Anonymous'
        self.exact_post    = None
        self.similar_posts = []

    def describe(self):
        data = {
            'id': self.id,
            'version': self.version,
            'image_url': self.image_url,
            'tags': self.tags,
            'rating': self.rating,
            'source': self.source,
            'image_token': self.image_token,
            'exact_post': self.exact_post,
            'similar_posts': self.similar_posts,
        }

        print(data)
