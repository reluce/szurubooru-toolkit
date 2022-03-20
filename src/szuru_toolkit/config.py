from tomlkit import parse


class Config:
    """Holds the options set in config.toml as attributes."""

    def __init__(self) -> None:
        """Parse the user config and set the object attributes accordingly."""

        with open('config.toml') as f:
            content = f.read()
            self.config = parse(content)

        for key, value in self.config.items():
            setattr(self, key, value)
