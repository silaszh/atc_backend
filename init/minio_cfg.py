import os

from dotenv import load_dotenv
from minio import Minio
from minio.commonconfig import ENABLED
from minio.error import S3Error
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration
from minio.notificationconfig import NotificationConfig, QueueConfig

load_dotenv()

client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False,
)

if not client.bucket_exists("atc"):
    client.make_bucket("atc")
    print("存储桶 'atc' 创建成功！")

rule = Rule(
    status=ENABLED,
    rule_id="cleanup_old_videos",
    expiration=Expiration(days=7),
)

lifecycle_config = LifecycleConfig([rule])
client.set_bucket_lifecycle("atc", lifecycle_config)

print("生命周期规则配置成功！")

config = NotificationConfig(
    queue_config_list=[
        QueueConfig(
            ["s3:ObjectCreated:*"],
            queue="arn:minio:sqs::primary:webhook",
        )
    ]
)

try:
    client.set_bucket_notification(bucket_name="atc", config=config)
    print("桶通知规则配置成功！")
except S3Error as exc:
    if exc.code == "InvalidArgument":
        print("桶通知规则配置失败：webhook ARN 未在 MinIO 服务端注册。")
        print(
            "请先在 MinIO 服务端配置 webhook 目标，再使用 ARN: arn:minio:sqs::primary:webhook。"
        )
