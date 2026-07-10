import httpx

from szurubooru_toolkit import config


class Sankaku:
    def __init__(self, transport: httpx.BaseTransport = None) -> None:
        """
        Initialize an httpx client for Sankaku.

        Args:
            transport (httpx.BaseTransport, optional): Custom transport, used for testing.
        """

        self.headers = {
            'Accept': 'application/vnd.sankaku.api+json;v=2',
            'Platform': 'web-app',
            'Api-Version': '2',
        }

        username = config.credentials['sankaku']['username']
        password = config.credentials['sankaku']['password']

        self.api_url = 'https://sankakuapi.com'
        if username and password:
            self.headers['Authorization'] = self._authenticate(username, password)

        self.client = httpx.Client(base_url=self.api_url, headers=self.headers, timeout=30, transport=transport)

    def _authenticate(self, username: str, password: str) -> str:
        """
        Authenticate with Sankaku and return the access token.

        Args:
            username (str): The username to authenticate with.
            password (str): The password to authenticate with.

        Returns:
            str: The access token.

        Raises:
            Exception: If the authentication fails.
        """

        url = self.api_url + '/auth/token'
        headers = {'Accept': 'application/vnd.sankaku.api+json;v=2'}
        data = {'login': username, 'password': password}

        response = httpx.post(url, headers=headers, json=data, timeout=30)
        data = response.json()

        if response.status_code >= 400 or not data.get('success'):
            raise Exception(data.get('error'))

        return 'Bearer ' + data['access_token']

    def search(self, query: str, limit: int = 100, page: int = 0) -> list | None:
        """
        Searches Sankaku for the given query.

        Args:
            query (str): The query to search for.
            limit (int): The maximum number of results to return. Defaults to 100.
            page (int): The page of results to return. Defaults to 1.

        Returns:
            list|None: The search results. None: If no results are found.
        """

        params = {
            'lang': 'en',
            'page': str(page),
            'limit': str(limit),
            'tags': query,
        }

        response = self.client.get('/posts', params=params)
        if response.is_success:
            return response.json()
        else:
            return None
