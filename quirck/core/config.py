from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings, Secret, URL


config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
DATABASE_URL = config("DATABASE_URL", cast=URL)
SECRET_KEY = config("SECRET_KEY", cast=Secret)
PORT = config("PORT", cast=int, default=12003)
ROOT_PATH = config("ROOT_PATH", cast=str, default="/")

SSO_CONFIGURATION_URL = config("SSO_CONFIGURATION_URL", cast=str)
SSO_CLIENT_ID = config("SSO_CLIENT_ID", cast=str)
SSO_CLIENT_SECRET = config("SSO_CLIENT_SECRET", cast=Secret)

ALLOWED_GROUPS = config("ALLOWED_GROUPS", cast=CommaSeparatedStrings)

APP_MODULE = config("APP_MODULE", cast=str)

S3_ENDPOINT_URL = config("S3_ENDPOINT_URL", cast=str)
S3_REGION_NAME = config("S3_REGION_NAME", cast=str, default="us-east-1")
S3_ACCESS_KEY_ID = config("S3_ACCESS_KEY_ID", cast=str)
S3_SECRET_ACCESS_KEY = config("S3_SECRET_ACCESS_KEY", cast=Secret)
S3_DEFAULT_BUCKET = config("S3_DEFAULT_BUCKET", cast=str)

VPN_HOST = config("VPN_HOST", cast=str)
