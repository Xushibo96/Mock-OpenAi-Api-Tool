"""
测试 PresetValidator 类
"""
import pytest
import json


class TestValidateJSON:
    """测试JSON格式验证"""

    def test_valid_json_object(self):
        """测试有效的JSON对象"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '{"id": "test", "data": "value"}'
        is_valid, parsed, error = PresetValidator.validate_json(json_str)

        assert is_valid is True
        assert parsed == {"id": "test", "data": "value"}
        assert error is None

    def test_valid_json_nested(self):
        """测试嵌套的JSON对象"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '{"outer": {"inner": {"deep": "value"}}}'
        is_valid, parsed, error = PresetValidator.validate_json(json_str)

        assert is_valid is True
        assert parsed["outer"]["inner"]["deep"] == "value"

    def test_invalid_json_syntax(self):
        """测试无效的JSON语法"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '{invalid json}'
        is_valid, parsed, error = PresetValidator.validate_json(json_str)

        assert is_valid is False
        assert parsed is None
        assert error is not None
        assert "JSON格式错误" in error

    def test_invalid_json_missing_quote(self):
        """测试缺少引号的JSON"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '{"key": value}'
        is_valid, parsed, error = PresetValidator.validate_json(json_str)

        assert is_valid is False
        assert error is not None

    def test_invalid_json_trailing_comma(self):
        """测试多余逗号的JSON"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '{"key": "value",}'
        is_valid, parsed, error = PresetValidator.validate_json(json_str)

        assert is_valid is False
        assert error is not None

    def test_empty_string(self):
        """测试空字符串"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        is_valid, parsed, error = PresetValidator.validate_json('')

        assert is_valid is False
        assert error is not None

    def test_json_array(self):
        """测试JSON数组"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '[{"a": 1}, {"b": 2}]'
        is_valid, parsed, error = PresetValidator.validate_json(json_str)

        assert is_valid is True
        assert isinstance(parsed, list)
        assert len(parsed) == 2


class TestValidateResponseObject:
    """测试响应对象验证"""

    def test_valid_dict(self):
        """测试有效的字典"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        obj = {"id": "test", "data": "value"}
        is_valid, error = PresetValidator.validate_response_object(obj)

        assert is_valid is True
        assert error is None

    def test_invalid_not_dict(self):
        """测试非字典类型"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        obj = "not a dict"
        is_valid, error = PresetValidator.validate_response_object(obj)

        assert is_valid is False
        assert error is not None
        assert "必须是JSON对象" in error

    def test_invalid_list(self):
        """测试列表类型"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        obj = [1, 2, 3]
        is_valid, error = PresetValidator.validate_response_object(obj)

        assert is_valid is False

    def test_empty_dict(self):
        """测试空字典"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        obj = {}
        is_valid, error = PresetValidator.validate_response_object(obj)

        assert is_valid is True


class TestValidateImportArray:
    """测试导入数组验证"""

    def test_valid_array(self):
        """测试有效的数组"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '[{"a": 1}, {"b": 2}, {"c": 3}]'
        is_valid, parsed, error = PresetValidator.validate_import_array(json_str)

        assert is_valid is True
        assert len(parsed) == 3
        assert error is None

    def test_empty_array(self):
        """测试空数组"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '[]'
        is_valid, parsed, error = PresetValidator.validate_import_array(json_str)

        assert is_valid is True
        assert len(parsed) == 0

    def test_invalid_not_array(self):
        """测试非数组类型"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '{"key": "value"}'
        is_valid, parsed, error = PresetValidator.validate_import_array(json_str)

        assert is_valid is False
        assert parsed is None
        assert "必须是JSON数组" in error

    def test_invalid_json_syntax(self):
        """测试无效JSON语法"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '[{invalid]'
        is_valid, parsed, error = PresetValidator.validate_import_array(json_str)

        assert is_valid is False
        assert error is not None


class TestValidateArrayElements:
    """测试数组元素验证"""

    def test_all_valid_elements(self):
        """测试所有元素有效"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        arr = [{"a": 1}, {"b": 2}, {"c": 3}]
        errors = PresetValidator.validate_array_elements(arr)

        assert len(errors) == 0

    def test_some_invalid_elements(self):
        """测试部分元素无效"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        arr = [
            {"valid": 1},
            "invalid string",
            {"valid": 2},
            123,
            {"valid": 3}
        ]
        errors = PresetValidator.validate_array_elements(arr)

        assert len(errors) == 2
        assert (1, "元素 1 不是有效的JSON对象") in errors
        assert (3, "元素 3 不是有效的JSON对象") in errors

    def test_all_invalid_elements(self):
        """测试所有元素无效"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        arr = ["string1", 123, True, None]
        errors = PresetValidator.validate_array_elements(arr)

        assert len(errors) == 4

    def test_empty_array(self):
        """测试空数组"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        arr = []
        errors = PresetValidator.validate_array_elements(arr)

        assert len(errors) == 0

    def test_nested_objects(self):
        """测试嵌套对象"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        arr = [
            {"outer": {"inner": "value"}},
            {"array": [1, 2, 3]},
            {"mixed": {"a": [1, {"b": 2}]}}
        ]
        errors = PresetValidator.validate_array_elements(arr)

        assert len(errors) == 0


class TestValidatorIntegration:
    """集成测试"""

    def test_full_import_validation_workflow(self):
        """测试完整的导入验证流程"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        # 模拟导入JSON文件内容
        json_content = '''
        [
            {"id": "resp1", "status_code": 200, "data": {"result": "success"}},
            {"id": "resp2", "status_code": 201, "data": {"result": "created"}},
            "invalid element",
            {"id": "resp3", "status_code": 400, "data": {"error": "bad request"}}
        ]
        '''

        # 第一步：验证是否为有效数组
        is_valid, parsed_array, error = PresetValidator.validate_import_array(json_content)
        assert is_valid is True

        # 第二步：验证数组元素
        element_errors = PresetValidator.validate_array_elements(parsed_array)
        assert len(element_errors) == 1
        assert element_errors[0][0] == 2  # 索引2的元素无效

        # 第三步：过滤有效元素
        valid_elements = [
            elem for idx, elem in enumerate(parsed_array)
            if not any(err[0] == idx for err in element_errors)
        ]

        assert len(valid_elements) == 3
        assert valid_elements[0]["id"] == "resp1"
        assert valid_elements[1]["id"] == "resp2"
        assert valid_elements[2]["id"] == "resp3"

    def test_error_message_details(self):
        """测试错误消息包含详细信息"""
        from mock_openai_tool.backend.preset_validator import PresetValidator

        json_str = '{"key": invalid}'
        is_valid, parsed, error = PresetValidator.validate_json(json_str)

        assert is_valid is False
        assert "JSON格式错误" in error
        # 错误信息应包含行号和列号
