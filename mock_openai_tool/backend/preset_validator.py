"""
PresetValidator - JSON格式验证器
"""
import json
from typing import Tuple, Optional, List


class PresetValidator:
    """预设响应验证器"""

    @staticmethod
    def validate_json(data: str) -> Tuple[bool, Optional[dict], Optional[str]]:
        """
        验证JSON字符串

        Args:
            data: JSON字符串

        Returns:
            (is_valid, parsed_data, error_message)
        """
        try:
            parsed = json.loads(data)
            return (True, parsed, None)
        except json.JSONDecodeError as e:
            error_msg = f"JSON格式错误: 行{e.lineno} 列{e.colno} - {e.msg}"
            return (False, None, error_msg)
        except Exception as e:
            error_msg = f"JSON格式错误: {str(e)}"
            return (False, None, error_msg)

    @staticmethod
    def validate_response_object(obj: dict) -> Tuple[bool, Optional[str]]:
        """
        验证响应对象基本结构

        Args:
            obj: 已解析的JSON对象

        Returns:
            (is_valid, error_message)
        """
        if not isinstance(obj, dict):
            return (False, "响应必须是JSON对象")

        # 基本验证通过
        return (True, None)

    @staticmethod
    def validate_import_array(data: str) -> Tuple[bool, Optional[List], Optional[str]]:
        """
        验证导入的JSON数组

        Args:
            data: JSON字符串

        Returns:
            (is_valid, parsed_array, error_message)
        """
        is_valid, parsed, error = PresetValidator.validate_json(data)
        if not is_valid:
            return (False, None, error)

        if not isinstance(parsed, list):
            return (False, None, "导入文件必须是JSON数组")

        return (True, parsed, None)

    @staticmethod
    def validate_array_elements(arr: List) -> List[Tuple[int, str]]:
        """
        验证数组中的每个元素

        Args:
            arr: JSON数组

        Returns:
            List of (index, error_message) for invalid elements
        """
        errors = []
        for idx, item in enumerate(arr):
            if not isinstance(item, dict):
                errors.append((idx, f"元素 {idx} 不是有效的JSON对象"))
        return errors
