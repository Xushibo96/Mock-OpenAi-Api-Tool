"""
REST API 路由
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
import json
from datetime import datetime

from .preset_validator import PresetValidator
from .bypass_config import ConfigValidationError

# 将在 main.py 中注入
queue_manager = None
websocket_broadcast = None
bypass_config_manager = None
bypass_handler = None

router = APIRouter(prefix="/api/preset-queue", tags=["preset-queue"])


class AddResponseRequest(BaseModel):
    response: dict
    status_code: int = 200


class BatchAddRequest(BaseModel):
    responses: List[dict]
    status_code: int = 200


@router.get("")
async def get_all_queues():
    """获取所有IP队列信息"""
    queues = await queue_manager.get_all_queues()
    return {
        "queues": {
            ip: {
                "count": len(items),
                "items": items
            }
            for ip, items in queues.items()
        }
    }


@router.get("/{ip}")
async def get_queue(ip: str):
    """获取指定IP的队列"""
    queue = await queue_manager.get_queue(ip)
    return {
        "ip": ip,
        "count": len(queue),
        "items": queue
    }


@router.post("/{ip}")
async def add_response(ip: str, req: AddResponseRequest):
    """添加单个响应到指定IP队列"""
    # 验证响应JSON
    is_valid, error = PresetValidator.validate_response_object(req.response)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    response_id = await queue_manager.add_response(
        ip, req.response, req.status_code
    )

    # 广播更新（如果有WebSocket）
    if websocket_broadcast:
        await websocket_broadcast("queue_updated", ip)

    return {
        "success": True,
        "response_id": response_id,
        "queue_length": queue_manager.get_queue_length(ip)
    }


@router.post("/{ip}/batch")
async def batch_add_responses(ip: str, req: BatchAddRequest):
    """批量添加响应到指定IP队列"""
    errors = PresetValidator.validate_array_elements(req.responses)

    added = []
    for idx, response in enumerate(req.responses):
        if not any(e[0] == idx for e in errors):
            response_id = await queue_manager.add_response(
                ip, response, req.status_code
            )
            added.append(response_id)

    # 广播更新
    if websocket_broadcast:
        await websocket_broadcast("queue_updated", ip)

    return {
        "success": True,
        "added_count": len(added),
        "failed_count": len(errors),
        "errors": [{"index": idx, "error": err} for idx, err in errors],
        "queue_length": queue_manager.get_queue_length(ip)
    }


@router.post("/{ip}/import")
async def import_queue(ip: str, file: UploadFile = File(...)):
    """从JSON文件导入队列"""
    # 检查文件大小
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="文件大小超过10MB限制")

    try:
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请使用UTF-8编码")

    # 验证JSON数组
    is_valid, parsed_array, error = PresetValidator.validate_import_array(content_str)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # 验证数组元素
    element_errors = PresetValidator.validate_array_elements(parsed_array)

    # 添加有效元素
    added = []
    for idx, response in enumerate(parsed_array):
        if not any(e[0] == idx for e in element_errors):
            response_id = await queue_manager.add_response(ip, response)
            added.append(response_id)

    # 广播更新
    if websocket_broadcast:
        await websocket_broadcast("queue_updated", ip)

    return {
        "success": True,
        "total": len(parsed_array),
        "added_count": len(added),
        "failed_count": len(element_errors),
        "errors": [{"index": idx, "error": err} for idx, err in element_errors]
    }


@router.get("/{ip}/export")
async def export_queue(ip: str):
    """导出指定IP队列为JSON文件"""
    queue = await queue_manager.get_queue(ip)

    if not queue:
        raise HTTPException(status_code=404, detail=f"IP {ip} 的队列不存在或为空")

    # 提取响应体
    responses = [item["response"] for item in queue]

    json_content = json.dumps(responses, ensure_ascii=False, indent=2)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"queue_{ip}_{timestamp}.json"

    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/export")
async def export_all_queues():
    """导出所有队列为JSON文件"""
    all_queues = await queue_manager.get_all_queues()

    if not all_queues:
        raise HTTPException(status_code=404, detail="没有可导出的队列")

    # 构建导出格式
    export_data = {}
    for ip, queue in all_queues.items():
        export_data[ip] = [item["response"] for item in queue]

    json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"queue_all_{timestamp}.json"

    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.delete("/{ip}/{response_id}")
async def delete_response(ip: str, response_id: str):
    """删除指定响应"""
    success = await queue_manager.delete_response(ip, response_id)
    if not success:
        raise HTTPException(status_code=404, detail="响应不存在")

    # 广播更新
    if websocket_broadcast:
        await websocket_broadcast("queue_updated", ip)

    return {"success": True}


@router.delete("/{ip}")
async def clear_queue(ip: str):
    """清空指定IP的队列"""
    success = await queue_manager.clear_queue(ip)
    if not success:
        raise HTTPException(status_code=404, detail="队列不存在")

    # 广播更新
    if websocket_broadcast:
        await websocket_broadcast("queue_updated", ip)

    return {"success": True}


@router.delete("")
async def clear_all_queues():
    """清空所有队列"""
    await queue_manager.clear_all_queues()

    # 广播更新
    if websocket_broadcast:
        await websocket_broadcast("all_queues_updated")

    return {"success": True}


# ============ Bypass API Routes ============

bypass_router = APIRouter(prefix="/api/bypass", tags=["bypass"])


class BypassConfigUpdateRequest(BaseModel):
    target_host: Optional[str] = None
    target_port: Optional[int] = None
    target_uri: Optional[str] = None
    api_key: Optional[str] = None
    use_https: Optional[bool] = None
    timeout: Optional[int] = None


@bypass_router.get("/config")
async def get_bypass_config():
    """获取 bypass 配置"""
    config = await bypass_config_manager.get_config()
    return {
        "enabled": config.enabled,
        "target_host": config.target_host,
        "target_port": config.target_port,
        "target_uri": config.target_uri,
        "use_https": config.use_https,
        "timeout": config.timeout,
        "api_key_configured": bool(config.api_key)
    }


@bypass_router.put("/config")
async def update_bypass_config(req: BypassConfigUpdateRequest):
    """更新 bypass 配置"""
    try:
        # 只传递非 None 的字段
        update_data = {
            k: v for k, v in req.dict().items()
            if v is not None
        }

        config = await bypass_config_manager.update_config(**update_data)

        # 广播配置更新事件
        if websocket_broadcast:
            await websocket_broadcast("bypass_config_updated")

        return {
            "enabled": config.enabled,
            "target_host": config.target_host,
            "target_port": config.target_port,
            "target_uri": config.target_uri,
            "use_https": config.use_https,
            "timeout": config.timeout,
            "api_key_configured": bool(config.api_key)
        }
    except ConfigValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@bypass_router.post("/enable")
async def enable_bypass():
    """启用 bypass 模式"""
    try:
        await bypass_config_manager.enable()

        # 广播配置更新事件
        if websocket_broadcast:
            await websocket_broadcast("bypass_config_updated")

        return {"enabled": True}
    except ConfigValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@bypass_router.post("/disable")
async def disable_bypass():
    """禁用 bypass 模式"""
    await bypass_config_manager.disable()

    # 广播配置更新事件
    if websocket_broadcast:
        await websocket_broadcast("bypass_config_updated")

    return {"enabled": False}
