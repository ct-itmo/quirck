import io
from pathlib import Path

import aioboto3
import botocore.client

from quirck.core import config


def get_session() -> aioboto3.Session:
    return aioboto3.Session(
        aws_access_key_id=config.S3_ACCESS_KEY_ID,
        aws_secret_access_key=config.S3_SECRET_ACCESS_KEY
    )


def get_client():
    return get_session().client(
        "s3",
        config.S3_REGION_NAME,
        endpoint_url=config.S3_ENDPOINT_URL,
        config=botocore.client.Config(signature_version='s3v4')
    )


def get_resource():
    return get_session().resource(
        "s3",
        config.S3_REGION_NAME,
        endpoint_url=config.S3_ENDPOINT_URL
    )


async def list_files(bucket_name: str, folder: str, user_id: int) -> list[str]:
    prefix = f"{folder}/{user_id}/"

    async with get_resource() as s3:
        bucket = await s3.Bucket(bucket_name)
        
        return [
            item.key[len(prefix):]
            async for item in bucket.objects.filter(Prefix=prefix)
        ]


async def get_url(bucket_name: str, folder: str, user_id: int, filename: str) -> str:
    path = f"{folder}/{user_id}/{filename}"

    async with get_client() as s3_client:
        return await s3_client.generate_presigned_url(
            ClientMethod="get_object",
            HttpMethod="GET",
            Params={
                "Bucket": bucket_name,
                "Key": path
            },
            ExpiresIn=3600
        )


async def upload_file(bucket_name: str, folder: str, user_id: int, filename: str, source: Path) -> str:
    path = f"{folder}/{user_id}/{filename}"

    async with get_resource() as s3:
        bucket = await s3.Bucket(bucket_name)

        await bucket.upload_file(source, path)

    return path


async def upload_bytes(bucket_name: str, folder: str, user_id: int, filename: str, content: bytes) -> str:
    path = f"{folder}/{user_id}/{filename}"

    async with get_resource() as s3:
        bucket = await s3.Bucket(bucket_name)

        await bucket.upload_fileobj(io.BytesIO(content), path)

    return path


__all__ = ["list_files", "get_url", "upload_file", "upload_bytes"]
