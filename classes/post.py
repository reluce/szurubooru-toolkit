class Post:
    def __init__(self, md5sum, id=None, image_url=None, version=None, tags=[]):
        self.id            = id
        self.version       = version
        self.image_url     = image_url
        self.image         = None
        self.image_token   = None
        self.tags          = tags
        self.rating        = 'unsafe'
        self.source        = 'Anonymous'
        self.exact_post    = None
        self.md5sum        = md5sum
        self.similar_posts = []
