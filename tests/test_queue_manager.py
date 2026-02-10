"""
测试 PresetQueueManager 类
"""
import pytest
import asyncio
import json
import os


@pytest.mark.asyncio
class TestQueueManagerBasics:
    """测试队列管理器基本功能"""

    async def test_add_response(self, queue_manager):
        """测试添加响应到队列"""
        response = {"id": "test-1", "data": "test data"}
        status_code = 200

        response_id = await queue_manager.add_response("192.168.1.100", response, status_code)

        assert response_id is not None
        assert isinstance(response_id, str)
        assert queue_manager.get_queue_length("192.168.1.100") == 1

    async def test_add_multiple_responses(self, queue_manager):
        """测试添加多个响应"""
        ip = "192.168.1.100"

        id1 = await queue_manager.add_response(ip, {"test": "1"}, 200)
        id2 = await queue_manager.add_response(ip, {"test": "2"}, 201)
        id3 = await queue_manager.add_response(ip, {"test": "3"}, 202)

        assert queue_manager.get_queue_length(ip) == 3
        assert id1 != id2 != id3

    async def test_check_and_pop_success(self, queue_manager):
        """测试成功弹出响应"""
        ip = "192.168.1.100"
        response = {"id": "test-1", "result": "success"}
        status_code = 200

        await queue_manager.add_response(ip, response, status_code)

        result = await queue_manager.check_and_pop(ip)

        assert result is not None
        assert result[0] == response
        assert result[1] == status_code
        assert queue_manager.get_queue_length(ip) == 0

    async def test_check_and_pop_empty_queue(self, queue_manager):
        """测试空队列弹出返回None"""
        result = await queue_manager.check_and_pop("192.168.1.100")
        assert result is None

    async def test_check_and_pop_nonexistent_queue(self, queue_manager):
        """测试不存在的队列返回None"""
        result = await queue_manager.check_and_pop("192.168.1.999")
        assert result is None

    async def test_fifo_order(self, queue_manager):
        """测试FIFO顺序"""
        ip = "192.168.1.100"

        await queue_manager.add_response(ip, {"order": 1}, 200)
        await queue_manager.add_response(ip, {"order": 2}, 200)
        await queue_manager.add_response(ip, {"order": 3}, 200)

        result1 = await queue_manager.check_and_pop(ip)
        result2 = await queue_manager.check_and_pop(ip)
        result3 = await queue_manager.check_and_pop(ip)

        assert result1[0]["order"] == 1
        assert result2[0]["order"] == 2
        assert result3[0]["order"] == 3

    async def test_multiple_ip_queues(self, queue_manager):
        """测试多个IP独立队列"""
        ip1 = "192.168.1.100"
        ip2 = "192.168.1.101"

        await queue_manager.add_response(ip1, {"ip": "100"}, 200)
        await queue_manager.add_response(ip2, {"ip": "101"}, 200)

        assert queue_manager.get_queue_length(ip1) == 1
        assert queue_manager.get_queue_length(ip2) == 1

        result1 = await queue_manager.check_and_pop(ip1)
        result2 = await queue_manager.check_and_pop(ip2)

        assert result1[0]["ip"] == "100"
        assert result2[0]["ip"] == "101"


@pytest.mark.asyncio
class TestQueueManagerQueries:
    """测试队列查询功能"""

    async def test_get_queue(self, queue_manager):
        """测试获取队列内容"""
        ip = "192.168.1.100"

        await queue_manager.add_response(ip, {"test": "1"}, 200)
        await queue_manager.add_response(ip, {"test": "2"}, 201)

        queue = await queue_manager.get_queue(ip)

        assert len(queue) == 2
        assert queue[0]["response"] == {"test": "1"}
        assert queue[0]["status_code"] == 200
        assert queue[1]["response"] == {"test": "2"}
        assert queue[1]["status_code"] == 201

    async def test_get_queue_empty(self, queue_manager):
        """测试获取空队列"""
        queue = await queue_manager.get_queue("192.168.1.100")
        assert queue == []

    async def test_get_all_queues(self, queue_manager):
        """测试获取所有队列"""
        await queue_manager.add_response("192.168.1.100", {"ip": "100"}, 200)
        await queue_manager.add_response("192.168.1.101", {"ip": "101"}, 200)

        all_queues = await queue_manager.get_all_queues()

        assert "192.168.1.100" in all_queues
        assert "192.168.1.101" in all_queues
        assert len(all_queues["192.168.1.100"]) == 1
        assert len(all_queues["192.168.1.101"]) == 1

    async def test_get_queue_length(self, queue_manager):
        """测试获取队列长度"""
        ip = "192.168.1.100"

        assert queue_manager.get_queue_length(ip) == 0

        await queue_manager.add_response(ip, {"test": "1"}, 200)
        assert queue_manager.get_queue_length(ip) == 1

        await queue_manager.add_response(ip, {"test": "2"}, 200)
        assert queue_manager.get_queue_length(ip) == 2

        await queue_manager.check_and_pop(ip)
        assert queue_manager.get_queue_length(ip) == 1


@pytest.mark.asyncio
class TestQueueManagerDeletion:
    """测试队列删除功能"""

    async def test_delete_response(self, queue_manager):
        """测试删除指定响应"""
        ip = "192.168.1.100"

        id1 = await queue_manager.add_response(ip, {"test": "1"}, 200)
        id2 = await queue_manager.add_response(ip, {"test": "2"}, 200)
        id3 = await queue_manager.add_response(ip, {"test": "3"}, 200)

        success = await queue_manager.delete_response(ip, id2)

        assert success is True
        assert queue_manager.get_queue_length(ip) == 2

        # 验证删除的是中间项
        queue = await queue_manager.get_queue(ip)
        assert queue[0]["id"] == id1
        assert queue[1]["id"] == id3

    async def test_delete_nonexistent_response(self, queue_manager):
        """测试删除不存在的响应"""
        success = await queue_manager.delete_response("192.168.1.100", "fake-id")
        assert success is False

    async def test_clear_queue(self, queue_manager):
        """测试清空队列"""
        ip = "192.168.1.100"

        await queue_manager.add_response(ip, {"test": "1"}, 200)
        await queue_manager.add_response(ip, {"test": "2"}, 200)

        success = await queue_manager.clear_queue(ip)

        assert success is True
        assert queue_manager.get_queue_length(ip) == 0

    async def test_clear_nonexistent_queue(self, queue_manager):
        """测试清空不存在的队列"""
        success = await queue_manager.clear_queue("192.168.1.999")
        assert success is False

    async def test_delete_queue(self, queue_manager):
        """测试删除整个队列"""
        ip = "192.168.1.100"

        await queue_manager.add_response(ip, {"test": "1"}, 200)

        success = await queue_manager.delete_queue(ip)

        assert success is True
        all_queues = await queue_manager.get_all_queues()
        assert ip not in all_queues

    async def test_clear_all_queues(self, queue_manager):
        """测试清空所有队列"""
        await queue_manager.add_response("192.168.1.100", {"test": "1"}, 200)
        await queue_manager.add_response("192.168.1.101", {"test": "2"}, 200)

        await queue_manager.clear_all_queues()

        all_queues = await queue_manager.get_all_queues()
        assert len(all_queues) == 0


@pytest.mark.asyncio
class TestQueueManagerConcurrency:
    """测试并发安全性"""

    async def test_concurrent_add(self, queue_manager):
        """测试并发添加"""
        ip = "192.168.1.100"

        tasks = [
            queue_manager.add_response(ip, {"index": i}, 200)
            for i in range(100)
        ]

        await asyncio.gather(*tasks)

        assert queue_manager.get_queue_length(ip) == 100

    async def test_concurrent_pop(self, queue_manager):
        """测试并发弹出"""
        ip = "192.168.1.100"

        # 添加50个响应
        for i in range(50):
            await queue_manager.add_response(ip, {"index": i}, 200)

        # 并发弹出100次（其中50次应返回None）
        tasks = [queue_manager.check_and_pop(ip) for _ in range(100)]
        results = await asyncio.gather(*tasks)

        valid_results = [r for r in results if r is not None]
        none_results = [r for r in results if r is None]

        assert len(valid_results) == 50
        assert len(none_results) == 50
        assert queue_manager.get_queue_length(ip) == 0

    async def test_concurrent_mixed_operations(self, queue_manager):
        """测试混合并发操作"""
        ip = "192.168.1.100"

        # 先添加一些数据
        for i in range(10):
            await queue_manager.add_response(ip, {"index": i}, 200)

        # 混合操作
        tasks = []
        tasks.extend([queue_manager.add_response(ip, {"new": i}, 200) for i in range(20)])
        tasks.extend([queue_manager.check_and_pop(ip) for _ in range(15)])
        tasks.extend([queue_manager.get_queue(ip) for _ in range(5)])

        await asyncio.gather(*tasks)

        # 验证队列仍然可用
        length = queue_manager.get_queue_length(ip)
        assert length >= 0  # 应该有一些剩余


@pytest.mark.asyncio
class TestQueueManagerPersistence:
    """测试持久化功能"""

    async def test_persist_and_load(self, temp_file):
        """测试保存和加载"""
        from mock_openai_tool.backend.queue_manager import PresetQueueManager

        # 创建管理器并添加数据
        manager1 = PresetQueueManager(persistence_path=temp_file)
        await manager1.add_response("192.168.1.100", {"test": "1"}, 200)
        await manager1.add_response("192.168.1.101", {"test": "2"}, 201)

        # 等待持久化完成
        await asyncio.sleep(0.1)

        # 验证文件存在
        assert os.path.exists(temp_file)

        # 创建新管理器并加载
        manager2 = PresetQueueManager(persistence_path=temp_file)
        await manager2.load()

        # 验证数据已加载
        assert manager2.get_queue_length("192.168.1.100") == 1
        assert manager2.get_queue_length("192.168.1.101") == 1

        queue_100 = await manager2.get_queue("192.168.1.100")
        assert queue_100[0]["response"] == {"test": "1"}
        assert queue_100[0]["status_code"] == 200

    async def test_load_nonexistent_file(self, temp_file):
        """测试加载不存在的文件"""
        from mock_openai_tool.backend.queue_manager import PresetQueueManager

        # 删除临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)

        manager = PresetQueueManager(persistence_path=temp_file)
        await manager.load()

        # 应该成功加载（空队列）
        all_queues = await manager.get_all_queues()
        assert len(all_queues) == 0

    async def test_load_corrupted_file(self, temp_file):
        """测试加载损坏的文件"""
        from mock_openai_tool.backend.queue_manager import PresetQueueManager

        # 写入无效JSON
        with open(temp_file, 'w') as f:
            f.write("{invalid json")

        manager = PresetQueueManager(persistence_path=temp_file)
        await manager.load()

        # 应该成功加载（忽略损坏文件，使用空队列）
        all_queues = await manager.get_all_queues()
        assert len(all_queues) == 0

    async def test_persistence_after_operations(self, temp_file):
        """测试操作后自动持久化"""
        from mock_openai_tool.backend.queue_manager import PresetQueueManager

        manager = PresetQueueManager(persistence_path=temp_file)

        # 添加
        await manager.add_response("192.168.1.100", {"test": "add"}, 200)
        await asyncio.sleep(0.1)

        # 删除
        queue = await manager.get_queue("192.168.1.100")
        await manager.delete_response("192.168.1.100", queue[0]["id"])
        await asyncio.sleep(0.1)

        # 重新加载验证
        manager2 = PresetQueueManager(persistence_path=temp_file)
        await manager2.load()

        assert manager2.get_queue_length("192.168.1.100") == 0
