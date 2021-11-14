class Post:
    def __init__(self, id=None, image_url=None, version=None, tags=[]):
        self.id            = id
        self.version       = version
        self.image_url     = image_url
        self.image_token   = None
        self.tags          = tags
        self.rating        = 'unsafe'
        self.source        = ''
        self.exact_post    = None
        self.similar_posts = []
