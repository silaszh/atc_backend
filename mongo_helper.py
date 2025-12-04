from typing import Any, Dict, Optional, List
from datetime import datetime

from pymongo import MongoClient, DESCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")
PERSONS_COLLECTION = "persons"
STATE_LOGS_COLLECTION = "state_logs"
MAX_LOGS_PER_PERSON = 10000


class MongoHelper:
    def __init__(self, uri: Optional[str] = None, db: Optional[str] = None):
        self.uri = uri or MONGO_URI
        self.db_name = db or MONGO_DB
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]
        self.persons_coll: Collection = self.db[PERSONS_COLLECTION]
        self.state_logs_coll: Collection = self.db[STATE_LOGS_COLLECTION]

        # 确保索引
        self.persons_coll.create_index("id", unique=True)
        self.state_logs_coll.create_index([("person_id", 1), ("timestamp", DESCENDING)])

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    # Persons 集合方法
    def create_person(self, person: Dict[str, Any]) -> Dict[str, Any]:
        if "id" not in person:
            raise ValueError("person must contain an 'id' field")

        try:
            res = self.persons_coll.insert_one(person)
            return self.persons_coll.find_one({"_id": res.inserted_id})
        except DuplicateKeyError:
            raise ValueError(f"Person with id {person['id']} already exists")

    def get_person_by_id(self, person_id: str) -> Optional[Dict[str, Any]]:
        return self.persons_coll.find_one({"id": person_id})

    def get_person_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self.persons_coll.find_one({"name": name})

    def update_person_last_login(self, person_id: str) -> Optional[Dict[str, Any]]:
        """更新员工的上次登录时间"""
        return self.persons_coll.find_one_and_update(
            {"id": person_id},
            {"$set": {"last_login_time": datetime.utcnow()}},
            return_document=ReturnDocument.AFTER,
        )

    def get_all_persons(self) -> List[Dict[str, Any]]:
        return list(self.persons_coll.find().sort("id", 1))

    # State logs 集合方法
    def insert_state_log(self, log: Dict[str, Any]) -> None:
        if "timestamp" in log:
            if isinstance(log["timestamp"], str):
                # 解析 "2025-11-14-17-06-08" 格式为 datetime
                parts = log["timestamp"].split("-")
                if len(parts) == 6:
                    log["timestamp"] = datetime(
                        int(parts[0]),
                        int(parts[1]),
                        int(parts[2]),
                        int(parts[3]),
                        int(parts[4]),
                        int(parts[5]),
                    )
        else:
            log["timestamp"] = datetime.utcnow()
        person_id = log["person_id"]

        self.state_logs_coll.insert_one(log)

        # 自动清理：每个人员只保留最新的 MAX_LOGS_PER_PERSON 条日志
        # 找到第 MAX_LOGS_PER_PERSON 条最新日志的时间戳
        cursor = (
            self.state_logs_coll.find({"person_id": person_id})
            .sort("timestamp", DESCENDING)
            .skip(MAX_LOGS_PER_PERSON - 1)
        )
        oldest_to_keep = list(cursor)
        if oldest_to_keep:
            cutoff_timestamp = oldest_to_keep[0]["timestamp"]
            self.state_logs_coll.delete_many(
                {"person_id": person_id, "timestamp": {"$lt": cutoff_timestamp}}
            )

    def get_state_logs_by_person_id(
        self, person_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return list(
            self.state_logs_coll.find({"person_id": person_id})
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )

    def get_latest_state_log(self, person_id: str) -> Optional[Dict[str, Any]]:
        return self.state_logs_coll.find_one(
            {"person_id": person_id}, sort=[("timestamp", DESCENDING)]
        )


def get_default_helper() -> MongoHelper:
    """返回使用默认配置的 MongoHelper 实例。"""
    return MongoHelper()
