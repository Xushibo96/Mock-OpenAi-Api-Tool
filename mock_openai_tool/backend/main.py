from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import uuid
import logging

# 导入队列管理器、bypass配置和API路由
from .queue_manager import PresetQueueManager
from .bypass_config import BypassConfigManager
from .bypass_handler import BypassHandler, BypassError
from . import api_routes

app = FastAPI()

# 启用跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock-queue")

# 全局管理器
queue_manager = None
bypass_config_manager = None
bypass_handler = None


# 条件性挂载前端（仅在目录存在时）
import os as _os
_frontend_path = "/app/mock_openai_tool/frontend"
if _os.path.exists(_frontend_path):
    app.mount("/frontend", StaticFiles(directory=_frontend_path), name="frontend")
elif _os.path.exists("mock_openai_tool/frontend"):
    app.mount("/frontend", StaticFiles(directory="mock_openai_tool/frontend"), name="frontend")

@app.get("/")
def index():
    # 如果前端文件存在则返回，否则返回简单消息
    frontend_index = "/app/mock_openai_tool/frontend/index.html"
    if _os.path.exists(frontend_index):
        return FileResponse(frontend_index)
    elif _os.path.exists("mock_openai_tool/frontend/index.html"):
        return FileResponse("mock_openai_tool/frontend/index.html")
    else:
        return {"message": "Mock OpenAI Tool API", "status": "running"}

# 启动时初始化全局变量
@app.on_event("startup")
async def initialize_globals():
    global pending_requests, current_request, request_futures, websocket_clients, queue_manager
    global bypass_config_manager, bypass_handler

    pending_requests = asyncio.Queue()
    current_request = None
    request_futures = {}
    websocket_clients = set()

    # 初始化队列管理器
    queue_manager = PresetQueueManager(persistence_path="preset_queues.json")
    await queue_manager.load()

    # 初始化 bypass 配置管理器和处理器
    bypass_config_manager = BypassConfigManager(config_file="bypass_config.json")
    bypass_handler = BypassHandler(config_manager=bypass_config_manager)

    # 注入到 API 路由模块
    api_routes.queue_manager = queue_manager
    api_routes.websocket_broadcast = broadcast_queue_update
    api_routes.bypass_config_manager = bypass_config_manager
    api_routes.bypass_handler = bypass_handler

    logger.info("Global variables initialized on startup.")
    logger.info(f"Loaded queue manager with {len(await queue_manager.get_all_queues())} queues")
    config = await bypass_config_manager.get_config()
    logger.info(f"Bypass mode: {'enabled' if config.enabled else 'disabled'}")


async def broadcast_websocket(message: dict):
    """
    通用WebSocket广播函数

    Args:
        message: 要广播的消息字典
    """
    disconnected_clients = set()
    for ws in websocket_clients:
        try:
            await ws.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send to WebSocket client: {e}")
            disconnected_clients.add(ws)

    # 清理断开的客户端
    websocket_clients.difference_update(disconnected_clients)


async def broadcast_queue_update(event_type: str, ip: str = None):
    """
    Phase 4: 广播队列更新到所有WebSocket客户端

    Args:
        event_type: 事件类型（queue_updated, all_queues_updated）
        ip: 相关的IP地址（可选）
    """
    message = {"type": event_type}
    if ip:
        message["ip"] = ip
    await broadcast_websocket(message)


# 注册 API 路由
app.include_router(api_routes.router)
app.include_router(api_routes.bypass_router)

async def _check_client_disconnect(request: Request, req_id: str):
    """
    定期检查客户端是否断开连接
    如果断开，自动清理请求
    """
    try:
        while True:
            await asyncio.sleep(1)  # 每秒检查一次
            if await request.is_disconnected():
                logger.warning(f"Client disconnected for request {req_id}")
                # 如果 future 还存在且未完成，设置为取消状态
                future = request_futures.get(req_id)
                if future and not future.done():
                    future.set_exception(asyncio.CancelledError("Client disconnected"))
                break
    except asyncio.CancelledError:
        # 正常取消，客户端已收到响应
        pass


async def _cleanup_current_request(req_id: str):
    """
    清理当前请求（如果匹配）并处理下一个请求
    """
    global current_request
    if current_request and current_request.get("id") == req_id:
        logger.info(f"Cleaning up current_request for {req_id}")
        current_request = None
        # 处理队列中的下一个请求
        await process_next_request()


async def handle_bypass_request(
    request_body: dict,
    headers: dict,
    client_ip: str
) -> JSONResponse:
    """处理 bypass 请求"""
    import time

    request_id = str(uuid.uuid4())
    start_time = time.time()

    # 构建目标 URL（用于展示）
    config = await bypass_config_manager.get_config()
    scheme = "https" if config.use_https else "http"
    if (config.use_https and config.target_port == 443) or \
       (not config.use_https and config.target_port == 80):
        target_url = f"{scheme}://{config.target_host}{config.target_uri}"
    else:
        target_url = f"{scheme}://{config.target_host}:{config.target_port}{config.target_uri}"

    # 通知前端请求开始
    await broadcast_websocket({
        "type": "bypass_request",
        "data": {
            "id": request_id,
            "timestamp": start_time,
            "client_ip": client_ip,
            "request_body": request_body,
            "target_url": target_url
        }
    })

    try:
        # 转发请求
        response_body, status_code, elapsed = await bypass_handler.forward_request(
            request_body, headers, client_ip
        )

        # 通知前端响应成功
        await broadcast_websocket({
            "type": "bypass_response",
            "data": {
                "id": request_id,
                "timestamp": time.time(),
                "status_code": status_code,
                "response_body": response_body,
                "elapsed_ms": elapsed * 1000,
                "success": True
            }
        })

        return JSONResponse(content=response_body, status_code=status_code)

    except BypassError as e:
        # 通知前端响应失败
        await broadcast_websocket({
            "type": "bypass_response",
            "data": {
                "id": request_id,
                "timestamp": time.time(),
                "status_code": 502,
                "response_body": {"error": e.message},
                "elapsed_ms": (time.time() - start_time) * 1000,
                "success": False,
                "error": e.message
            }
        })

        return JSONResponse(
            content={"error": e.message},
            status_code=502
        )


@app.post("/v1/chat/completions")
async def handle_completion(request: Request):
    body = await request.json()
    client_ip = request.client.host
    client_port = request.client.port
    req_id = str(uuid.uuid4())

    # Priority 1: Check bypass mode (highest priority)
    if await bypass_config_manager.is_enabled():
        return await handle_bypass_request(body, dict(request.headers), client_ip)

    # Priority 2: 检查预设队列，如果有预设响应则直接返回
    preset_result = await queue_manager.check_and_pop(client_ip)
    if preset_result is not None:
        response_data, status_code = preset_result
        logger.info(f"Auto-response from preset queue for {client_ip}: {status_code}")

        # 广播队列更新（队列被消费）
        await broadcast_queue_update("queue_updated", client_ip)

        # 广播已完成的请求到前端（左侧历史记录）
        completed_data = {
            "type": "completed_request",
            "data": {
                "id": req_id,
                "ip": client_ip,
                "port": client_port,
                "body": body,
                "response": response_data,
                "status_code": status_code
            }
        }
        for ws in websocket_clients:
            try:
                await ws.send_json(completed_data)
            except Exception as e:
                logger.warning(f"Failed to send completed_request to WebSocket: {e}")

        return JSONResponse(content=response_data, status_code=status_code)

    # 队列为空，进入手动模式
    future = asyncio.get_event_loop().create_future()
    request_futures[req_id] = future

    request_obj = {
        "id": req_id,
        "ip": client_ip,
        "port": client_port,
        "method": "POST",
        "path": "/v1/completions",
        "headers": dict(request.headers),
        "body": body,
        "timestamp": str(asyncio.get_event_loop().time()),
        "status": "pending"
    }

    await pending_requests.put(request_obj)
    logger.info(f"Queued request: {req_id} from {client_ip}:{client_port}")
    await process_next_request()

    try:
        # 创建客户端断开检测任务
        disconnect_task = asyncio.create_task(_check_client_disconnect(request, req_id))

        try:
            response_data, status_code = await asyncio.wait_for(future, timeout=300)
            return JSONResponse(content=response_data, status_code=status_code)
        finally:
            # 取消断开检测任务
            disconnect_task.cancel()
            try:
                await disconnect_task
            except asyncio.CancelledError:
                pass

    except asyncio.CancelledError:
        logger.warning(f"Request {req_id} cancelled (client disconnected)")
        return JSONResponse(content={"error": "Request cancelled - client disconnected"}, status_code=499)
    except asyncio.TimeoutError:
        logger.warning(f"Request {req_id} timed out")
        return JSONResponse(content={"error": "Timeout waiting for mock response"}, status_code=504)
    finally:
        # 清理 future
        request_futures.pop(req_id, None)

        # 如果这是当前正在处理的请求，清空并处理下一个
        await _cleanup_current_request(req_id)


async def process_next_request():
    global current_request
    if current_request is not None or pending_requests.empty():
        return

    current_request = await pending_requests.get()
    logger.info(f"Processing request: {current_request['id']}")

    for ws in websocket_clients:
        await ws.send_json({
            "type": "new_request",
            "data": current_request
        })



@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global websocket_clients, current_request
    await ws.accept()
    websocket_clients.add(ws)
    
    if current_request:
        await ws.send_json({
            "type": "new_request",
            "data": current_request
        })

    try:
        while True:
            msg = await ws.receive_json()
            if msg["type"] == "send_response":
                
                req_id = msg["id"]
                status_code = msg.get("status_code", 200)
                response_data = msg["response"]

                future = request_futures.get(req_id)
                if future and not future.done():
                    future.set_result((response_data, status_code))
                    logging.info(f"Completed request: {req_id} → {status_code}")

                    # ✅ 确保在清空 current_request 之前发送
                    completed_data = {
                        "type": "completed_request",
                        "data": {
                            "id": req_id,
                            "ip": current_request["ip"],
                            "port": current_request["port"],
                            "body": current_request["body"],
                            "response": response_data,
                            "status_code": status_code
                        }
                    }

                    for ws_client in websocket_clients:
                        await ws_client.send_json(completed_data)

                    current_request = None
                    await process_next_request()

    except WebSocketDisconnect:
        websocket_clients.remove(ws)

    