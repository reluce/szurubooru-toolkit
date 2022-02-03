from classes.api import API
from classes.user_input import UserInput

def main():
    """
    Create or update tags
    """

    user_input = UserInput()
    user_input.parse_config()
    user_input.parse_input()
    api = API(
        szuru_address    = user_input.szuru_address,
        szuru_api_token  = user_input.szuru_api_token,
        szuru_public     = user_input.szuru_public,
    )

    api.create_tags()

if __name__ == '__main__':
    main()
