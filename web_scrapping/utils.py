import os
from dotenv import load_dotenv, find_dotenv


def get_absolute_current_path():
    return os.path.dirname(os.path.abspath(__file__))


def load_env():
    _ = load_dotenv(find_dotenv())


def get_env_key(key_name):
    load_env()
    return os.getenv(key_name)


if __name__ == "__main__":
    print(get_absolute_current_path())
