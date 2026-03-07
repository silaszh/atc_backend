from datetime import timedelta
import os

from dotenv import load_dotenv
from minio import Minio

load_dotenv()

minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False,
)


def get_video_url(video_path):
    filename = os.path.basename(video_path)
    return minio_client.presigned_get_object(
        bucket_name="atc", object_name=filename, expires=timedelta(days=30)
    )
