"""
PresetQueueManager - 基于源IP的预设响应队列管理器
"""
from collections import deque
from typing import Dict, Deque, Optional, List, Tuple
import uuid
import asyncio
import json
import os
import logging
import time

logger = logging.getLogger("preset-queue")


class PresetQueueManager:
    """
    基于源IP的预设响应队列管理器

    数据结构:
        _queues: Dict[str, Deque[PresetResponse]]
            键: IP地址 (str)
            值: 响应队列 (Deque)
    """

    def __init__(self, persistence_path: str = "preset_queues.json"):
        self._queues: Dict[str, Deque] = {}
        self._lock = asyncio.Lock()
        self._persistence_path = persistence_path

    async def add_response(self, ip: str, response: dict, status_code: int = 200) -> str:
        """
        添加响应到指定IP队列

        Args:
            ip: 源IP地址
            response: 响应体（已验证的JSON）
            status_code: HTTP状态码

        Returns:
            response_id: 分配的唯一ID
        """
        async with self._lock:
            if ip not in self._queues:
                self._queues[ip] = deque()

            response_id = str(uuid.uuid4())
            preset_item = {
                "id": response_id,
                "response": response,
                "status_code": status_code,
                "created_at": time.time()
            }

            self._queues[ip].append(preset_item)
            await self._persist_async()
            return response_id

    async def check_and_pop(self, ip: str) -> Optional[Tuple[dict, int]]:
        """
        检查并弹出指定IP的队列头部响应

        Args:
            ip: 源IP地址

        Returns:
            (response, status_code) 或 None（队列为空或不存在）
        """
        async with self._lock:
            if ip not in self._queues or not self._queues[ip]:
                return None

            preset_item = self._queues[ip].popleft()
            await self._persist_async()
            return (preset_item["response"], preset_item["status_code"])

    async def get_queue(self, ip: str) -> List[dict]:
        """获取指定IP的队列内容（不移除）"""
        async with self._lock:
            if ip not in self._queues:
                return []
            return list(self._queues[ip])

    async def get_all_queues(self) -> Dict[str, List[dict]]:
        """获取所有队列"""
        async with self._lock:
            return {ip: list(queue) for ip, queue in self._queues.items()}

    async def delete_response(self, ip: str, response_id: str) -> bool:
        """删除指定响应"""
        async with self._lock:
            if ip not in self._queues:
                return False

            original_len = len(self._queues[ip])
            self._queues[ip] = deque([
                item for item in self._queues[ip]
                if item["id"] != response_id
            ])

            if len(self._queues[ip]) < original_len:
                await self._persist_async()
                return True
            return False

    async def clear_queue(self, ip: str) -> bool:
        """清空指定IP队列"""
        async with self._lock:
            if ip in self._queues:
                self._queues[ip].clear()
                await self._persist_async()
                return True
            return False

    async def delete_queue(self, ip: str) -> bool:
        """删除整个IP队列"""
        async with self._lock:
            if ip in self._queues:
                del self._queues[ip]
                await self._persist_async()
                return True
            return False

    async def clear_all_queues(self):
        """清空所有队列"""
        async with self._lock:
            self._queues.clear()
            await self._persist_async()

    def get_queue_length(self, ip: str) -> int:
        """获取队列长度（同步，不需要锁）"""
        return len(self._queues.get(ip, []))

    async def _persist_async(self):
        """异步持久化到文件"""
        # 在后台任务中执行，避免阻塞
        asyncio.create_task(self._persist())

    async def _persist(self):
        """持久化队列到JSON文件"""
        try:
            data = {
                ip: list(queue)
                for ip, queue in self._queues.items()
            }
            with open(self._persistence_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist queues: {e}")

    async def load(self):
        """从文件加载队列"""
        try:
            if os.path.exists(self._persistence_path):
                with open(self._persistence_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._queues = {
                        ip: deque(queue)
                        for ip, queue in data.items()
                    }
                logger.info(f"Loaded {len(self._queues)} queues from {self._persistence_path}")
        except Exception as e:
            logger.error(f"Failed to load queues: {e}")
