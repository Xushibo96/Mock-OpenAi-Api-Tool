"""
Pytest configuration and shared fixtures
"""
import pytest
import asyncio
import tempfile
import os


@pytest.fixture
def temp_file():
    """提供临时文件路径"""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    # 清理
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
async def queue_manager(temp_file):
    """提供队列管理器实例（测试用）"""
    from mock_openai_tool.backend.queue_manager import PresetQueueManager
    manager = PresetQueueManager(persistence_path=temp_file)
    yield manager
