from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings, Secret, URL


config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
DATABASE_URL = config("DATABASE_URL", cast=URL)
PORT = config("PORT", cast=int, default=12003)
ROOT_PATH = config("ROOT_PATH", cast=str, default="/")

SECRET_KEY = config("SECRET_KEY", cast=Secret)
SESSION_COOKIE_NAME = config("SESSION_COOKIE_NAME", cast=str, default="session")
SESSION_COOKIE_PATH = config("SESSION_COOKIE_PATH", cast=str, default="/")

SSO_CONFIGURATION_URL = config("SSO_CONFIGURATION_URL", cast=str)
SSO_CLIENT_ID = config("SSO_CLIENT_ID", cast=str)
SSO_CLIENT_SECRET = config("SSO_CLIENT_SECRET", cast=Secret)

ALLOWED_GROUPS = config("ALLOWED_GROUPS", cast=CommaSeparatedStrings)

APP_MODULE = config("APP_MODULE", cast=str)
