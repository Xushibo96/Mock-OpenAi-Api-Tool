"""
测试 REST API 端点
"""
import pytest
import json
import tempfile
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建测试客户端"""
    # 延迟导入以避免循环依赖
    from mock_openai_tool.backend.main import app
    return TestClient(app)


class TestGetQueues:
    """测试获取队列API"""

    def test_get_all_queues_empty(self, client):
        """测试获取空队列列表"""
        response = client.get("/api/preset-queue")
        assert response.status_code == 200
        data = response.json()
        assert "queues" in data
        assert isinstance(data["queues"], dict)

    def test_get_all_queues_with_data(self, client):
        """测试获取有数据的队列列表"""
        # 先添加一些数据
        client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"test": "data1"},
            "status_code": 200
        })
        client.post("/api/preset-queue/192.168.1.101", json={
            "response": {"test": "data2"},
            "status_code": 201
        })

        response = client.get("/api/preset-queue")
        assert response.status_code == 200
        data = response.json()
        assert "192.168.1.100" in data["queues"]
        assert "192.168.1.101" in data["queues"]
        assert data["queues"]["192.168.1.100"]["count"] == 1
        assert data["queues"]["192.168.1.101"]["count"] == 1

    def test_get_specific_queue(self, client):
        """测试获取指定IP队列"""
        # 添加数据
        client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"id": "test-1"},
            "status_code": 200
        })

        response = client.get("/api/preset-queue/192.168.1.100")
        assert response.status_code == 200
        data = response.json()
        assert data["ip"] == "192.168.1.100"
        assert data["count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["response"]["id"] == "test-1"

    def test_get_nonexistent_queue(self, client):
        """测试获取不存在的队列"""
        response = client.get("/api/preset-queue/192.168.1.999")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["items"] == []


class TestAddResponse:
    """测试添加响应API"""

    def test_add_valid_response(self, client):
        """测试添加有效响应"""
        response = client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"id": "chatcmpl-1", "result": "success"},
            "status_code": 200
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "response_id" in data
        assert data["queue_length"] == 1

    def test_add_response_with_custom_status_code(self, client):
        """测试添加自定义状态码的响应"""
        response = client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"error": "not found"},
            "status_code": 404
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_add_invalid_response_not_dict(self, client):
        """测试添加非字典响应"""
        response = client.post("/api/preset-queue/192.168.1.100", json={
            "response": "not a dict",
            "status_code": 200
        })

        assert response.status_code == 400
        assert "必须是JSON对象" in response.json()["detail"]

    def test_add_multiple_responses(self, client):
        """测试添加多个响应"""
        for i in range(5):
            response = client.post("/api/preset-queue/192.168.1.100", json={
                "response": {"index": i},
                "status_code": 200
            })
            assert response.status_code == 200

        # 验证队列长度
        queue = client.get("/api/preset-queue/192.168.1.100")
        assert queue.json()["count"] == 5


class TestBatchAdd:
    """测试批量添加API"""

    def test_batch_add_all_valid(self, client):
        """测试批量添加全部有效"""
        response = client.post("/api/preset-queue/192.168.1.100/batch", json={
            "responses": [
                {"id": "resp1"},
                {"id": "resp2"},
                {"id": "resp3"}
            ],
            "status_code": 200
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["added_count"] == 3
        assert data["failed_count"] == 0
        assert len(data["errors"]) == 0

    def test_batch_add_partial_valid(self, client):
        """测试批量添加部分有效"""
        response = client.post("/api/preset-queue/192.168.1.100/batch", json={
            "responses": [
                {"id": "resp1"},
                "invalid string",
                {"id": "resp2"},
                123,
                {"id": "resp3"}
            ],
            "status_code": 200
        })

        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 3
        assert data["failed_count"] == 2
        assert len(data["errors"]) == 2

    def test_batch_add_all_invalid(self, client):
        """测试批量添加全部无效"""
        response = client.post("/api/preset-queue/192.168.1.100/batch", json={
            "responses": ["str1", "str2", 123],
            "status_code": 200
        })

        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 0
        assert data["failed_count"] == 3


class TestImportExport:
    """测试导入导出API"""

    def test_import_valid_json_file(self, client):
        """测试导入有效JSON文件"""
        json_data = [
            {"id": "resp1", "data": "value1"},
            {"id": "resp2", "data": "value2"},
            {"id": "resp3", "data": "value3"}
        ]

        # 创建临时文件
        import io
        file_content = json.dumps(json_data, ensure_ascii=False)
        file = io.BytesIO(file_content.encode('utf-8'))

        response = client.post(
            "/api/preset-queue/192.168.1.100/import",
            files={"file": ("test.json", file, "application/json")}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 3
        assert data["added_count"] == 3
        assert data["failed_count"] == 0

    def test_import_partial_valid(self, client):
        """测试导入部分有效的文件"""
        json_data = [
            {"id": "resp1"},
            "invalid",
            {"id": "resp2"},
            123
        ]

        import io
        file_content = json.dumps(json_data)
        file = io.BytesIO(file_content.encode('utf-8'))

        response = client.post(
            "/api/preset-queue/192.168.1.100/import",
            files={"file": ("test.json", file, "application/json")}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 2
        assert data["failed_count"] == 2

    def test_import_invalid_json(self, client):
        """测试导入无效JSON"""
        import io
        file = io.BytesIO(b'{invalid json}')

        response = client.post(
            "/api/preset-queue/192.168.1.100/import",
            files={"file": ("test.json", file, "application/json")}
        )

        assert response.status_code == 400
        assert "JSON格式错误" in response.json()["detail"]

    def test_import_not_array(self, client):
        """测试导入非数组JSON"""
        import io
        file = io.BytesIO(b'{"key": "value"}')

        response = client.post(
            "/api/preset-queue/192.168.1.100/import",
            files={"file": ("test.json", file, "application/json")}
        )

        assert response.status_code == 400
        assert "必须是JSON数组" in response.json()["detail"]

    def test_export_queue(self, client):
        """测试导出队列"""
        # 先添加一些数据
        client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"id": "resp1"},
            "status_code": 200
        })
        client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"id": "resp2"},
            "status_code": 201
        })

        response = client.get("/api/preset-queue/192.168.1.100/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers["content-disposition"]
        assert "queue_192.168.1.100_" in response.headers["content-disposition"]

        # 验证导出的内容
        exported_data = response.json()
        assert len(exported_data) == 2
        assert exported_data[0]["id"] == "resp1"
        assert exported_data[1]["id"] == "resp2"

    def test_export_empty_queue(self, client):
        """测试导出空队列"""
        response = client.get("/api/preset-queue/192.168.1.999/export")
        assert response.status_code == 404

    def test_export_all_queues(self, client):
        """测试导出所有队列"""
        # 添加多个IP的数据
        client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"ip": "100"},
            "status_code": 200
        })
        client.post("/api/preset-queue/192.168.1.101", json={
            "response": {"ip": "101"},
            "status_code": 200
        })

        response = client.get("/api/preset-queue/export")

        assert response.status_code == 200
        exported_data = response.json()
        assert "192.168.1.100" in exported_data
        assert "192.168.1.101" in exported_data
        assert len(exported_data["192.168.1.100"]) == 1
        assert len(exported_data["192.168.1.101"]) == 1


class TestDeleteOperations:
    """测试删除操作API"""

    def test_delete_response(self, client):
        """测试删除指定响应"""
        # 添加响应
        add_response = client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"test": "data"},
            "status_code": 200
        })
        response_id = add_response.json()["response_id"]

        # 删除响应
        delete_response = client.delete(f"/api/preset-queue/192.168.1.100/{response_id}")

        assert delete_response.status_code == 200
        assert delete_response.json()["success"] is True

        # 验证已删除
        queue = client.get("/api/preset-queue/192.168.1.100")
        assert queue.json()["count"] == 0

    def test_delete_nonexistent_response(self, client):
        """测试删除不存在的响应"""
        response = client.delete("/api/preset-queue/192.168.1.100/fake-id")
        assert response.status_code == 404

    def test_clear_queue(self, client):
        """测试清空队列"""
        # 添加多个响应
        for i in range(5):
            client.post("/api/preset-queue/192.168.1.100", json={
                "response": {"index": i},
                "status_code": 200
            })

        # 清空队列
        response = client.delete("/api/preset-queue/192.168.1.100")

        assert response.status_code == 200
        assert response.json()["success"] is True

        # 验证已清空
        queue = client.get("/api/preset-queue/192.168.1.100")
        assert queue.json()["count"] == 0

    def test_clear_all_queues(self, client):
        """测试清空所有队列"""
        # 添加多个IP的数据
        client.post("/api/preset-queue/192.168.1.100", json={
            "response": {"ip": "100"},
            "status_code": 200
        })
        client.post("/api/preset-queue/192.168.1.101", json={
            "response": {"ip": "101"},
            "status_code": 200
        })

        # 清空所有
        response = client.delete("/api/preset-queue")

        assert response.status_code == 200
        assert response.json()["success"] is True

        # 验证所有队列已清空
        all_queues = client.get("/api/preset-queue")
        assert len(all_queues.json()["queues"]) == 0


class TestImportExportRoundtrip:
    """测试导入导出往返"""

    def test_export_then_import(self, client):
        """测试导出后再导入"""
        # 添加数据
        original_data = [
            {"id": "resp1", "data": "value1"},
            {"id": "resp2", "data": "value2"}
        ]

        for item in original_data:
            client.post("/api/preset-queue/192.168.1.100", json={
                "response": item,
                "status_code": 200
            })

        # 导出
        export_response = client.get("/api/preset-queue/192.168.1.100/export")
        exported_data = export_response.json()

        # 清空队列
        client.delete("/api/preset-queue/192.168.1.100")

        # 重新导入
        import io
        file_content = json.dumps(exported_data)
        file = io.BytesIO(file_content.encode('utf-8'))

        import_response = client.post(
            "/api/preset-queue/192.168.1.100/import",
            files={"file": ("test.json", file, "application/json")}
        )

        assert import_response.status_code == 200
        assert import_response.json()["added_count"] == 2

        # 验证数据一致
        queue = client.get("/api/preset-queue/192.168.1.100")
        items = queue.json()["items"]
        assert len(items) == 2
        assert items[0]["response"]["id"] == "resp1"
        assert items[1]["response"]["id"] == "resp2"
