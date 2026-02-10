# Mock OpenAI API Tool

<div align="center">

**A powerful OpenAI API mocking tool with manual and automatic response modes**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.127.0-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-brightgreen.svg)](https://www.docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Quick Start](#-quick-start) • [Features](#-key-features) • [Documentation](#-usage-guide) • [API Reference](#-api-documentation)

</div>

---

## 📖 Overview

Mock OpenAI Tool is a testing and development tool that intercepts and simulates OpenAI API responses. It provides flexible response management with both real-time manual responses and pre-configured automatic response queues.

**Perfect for:**

- 🧪 **API Testing & Debugging** - Test without calling the real OpenAI API
- 🎯 **Behavior Simulation** - Simulate various response scenarios (success, failure, rate limits, etc.)
- 📊 **Offline Development** - Develop without internet connectivity
- 🔄 **Automated Testing** - Pre-set response queues for automated test scenarios
- 💰 **Cost Savings** - Avoid API call costs during development

## ✨ Key Features

### 🎭 Dual Response Modes

- **Manual Response Mode** - Real-time response construction via web interface
  - WebSocket real-time communication
  - Visual JSON editor
  - Pre-built response templates
  - Custom HTTP status codes

- **Automatic Response Mode** - Preset queue-based auto responses
  - IP-based isolated queues
  - FIFO (First In First Out) ordering
  - Custom status codes (200, 429, 500, etc.)
  - Persistent storage across restarts

### 🎨 Modern Web Interface

- 📱 Responsive design for all screen sizes
- 🔄 Real-time updates without page refresh
- 📋 Request history with expandable cards
- 📂 Queue import/export (JSON format)
- 🎯 Batch operations support

### 🚀 High-Performance Architecture

- ⚡ Async I/O (AsyncIO)
- 🔐 Concurrency-safe (AsyncIO Locks)
- 💾 JSON file persistence
- 🎪 O(1) queue operation performance

---

## 🚀 Quick Start

### Method 1: Using Docker (Recommended)

**Fastest way to get started:**

```bash
# Build the image
docker build -t mock-openai-tool:latest .

# Run the container
docker run -d -p 8088:8000 --name mock-openai-tool mock-openai-tool:latest

# Access the web interface
open http://localhost:8088
```

### Method 2: Local Development

**For development and debugging:**

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/mock-openai-tool.git
cd mock-openai-tool

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn mock_openai_tool.backend.main:app --host 0.0.0.0 --port 8000

# 4. Access the web interface
open http://localhost:8000
```

### 🎯 Quick Test

**Send a test request:**

```bash
curl -X POST http://localhost:8088/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

**In the web interface:**
1. Open http://localhost:8088
2. Left panel shows the received request
3. Right panel - select "Manual Response" tab
4. Construct response and click "Send Response"

---

## 📚 Usage Guide

### Scenario 1: Manual Response Mode

**Use case:** Real-time debugging, flexible response construction

```bash
# 1. Send API request (will wait for manual response)
curl -X POST http://localhost:8088/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Explain quantum computing"}]
  }' &

# 2. In the web interface:
#    - View the request in the left "Current Request" panel
#    - Edit response in the right "Manual Response" tab
#    - Click "Send Response"

# 3. The curl request receives the response immediately
```

### Scenario 2: Automatic Response Mode (Preset Queues)

**Use case:** Automated testing, batch test scenarios

#### 2.1 Add Single Response to Queue

```bash
curl -X POST http://localhost:8088/api/preset-queue/192.168.1.100 \
  -H "Content-Type: application/json" \
  -d '{
    "response": {
      "id": "chatcmpl-test-1",
      "object": "chat.completion",
      "choices": [{
        "message": {
          "role": "assistant",
          "content": "This is a preset response!"
        }
      }]
    },
    "status_code": 200
  }'
```

#### 2.2 Batch Add Responses

```bash
curl -X POST http://localhost:8088/api/preset-queue/192.168.1.100/batch \
  -H "Content-Type: application/json" \
  -d '{
    "responses": [
      {"id": "resp-1", "choices": [{"message": {"content": "Response 1"}}]},
      {"id": "resp-2", "choices": [{"message": {"content": "Response 2"}}]}
    ],
    "status_code": 200
  }'
```

#### 2.3 Import from File

```bash
# Prepare JSON file
cat > queue.json <<EOF
[
  {"id": "chatcmpl-1", "choices": [{"message": {"content": "Auto response 1"}}]},
  {"id": "chatcmpl-2", "choices": [{"message": {"content": "Auto response 2"}}]}
]
EOF

# Import to queue
curl -X POST http://localhost:8088/api/preset-queue/192.168.1.100/import \
  -F "file=@queue.json"
```

#### 2.4 Test Auto-Response

```bash
# First request gets first response from queue
curl -X POST http://localhost:8088/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Test"}]}'

# Second request gets second response
curl -X POST http://localhost:8088/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Test"}]}'

# When queue is empty, switches to manual mode
```

### Scenario 3: Simulate Error Responses

**Simulate rate limiting (429):**

```bash
curl -X POST http://localhost:8088/api/preset-queue/192.168.1.100 \
  -H "Content-Type: application/json" \
  -d '{
    "response": {"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
    "status_code": 429
  }'
```

**Simulate server error (500):**

```bash
curl -X POST http://localhost:8088/api/preset-queue/192.168.1.100 \
  -H "Content-Type: application/json" \
  -d '{
    "response": {"error": {"message": "Internal server error", "type": "server_error"}},
    "status_code": 500
  }'
```

---

## 🔌 API Documentation

### OpenAI Compatible Endpoint

#### POST `/v1/chat/completions`

**Function:** Receives OpenAI-style chat requests

**Response Logic:**
1. Check client IP's preset queue
2. If queue has items: Return first response (FIFO)
3. If queue is empty: Enter manual mode and wait for response (300s timeout)

### Preset Queue Management API

All queue management endpoints are prefixed with `/api/preset-queue`

#### GET `/api/preset-queue` - Get all queues

```bash
curl http://localhost:8088/api/preset-queue
```

#### GET `/api/preset-queue/{ip}` - Get specific IP queue

```bash
curl http://localhost:8088/api/preset-queue/192.168.1.100
```

#### POST `/api/preset-queue/{ip}` - Add single response

```bash
curl -X POST http://localhost:8088/api/preset-queue/192.168.1.100 \
  -H "Content-Type: application/json" \
  -d '{"response": {...}, "status_code": 200}'
```

#### POST `/api/preset-queue/{ip}/batch` - Batch add responses

```bash
curl -X POST http://localhost:8088/api/preset-queue/192.168.1.100/batch \
  -H "Content-Type: application/json" \
  -d '{"responses": [{...}, {...}], "status_code": 200}'
```

#### POST `/api/preset-queue/{ip}/import` - Import JSON file

```bash
curl -X POST http://localhost:8088/api/preset-queue/192.168.1.100/import \
  -F "file=@queue.json"
```

#### GET `/api/preset-queue/{ip}/export` - Export queue

```bash
curl http://localhost:8088/api/preset-queue/192.168.1.100/export -o queue.json
```

#### DELETE `/api/preset-queue/{ip}` - Clear queue

```bash
curl -X DELETE http://localhost:8088/api/preset-queue/192.168.1.100
```

#### DELETE `/api/preset-queue` - Clear all queues

```bash
curl -X DELETE http://localhost:8088/api/preset-queue
```

### WebSocket Interface

#### WS `/ws` - Real-time bidirectional communication

**Event types clients receive:**

| Event Type | Description | Data Fields |
|-----------|-------------|-------------|
| `new_request` | New API request (manual mode) | `id`, `ip`, `port`, `body` |
| `completed_request` | Request completed | `id`, `ip`, `port`, `body`, `response`, `status_code` |
| `queue_updated` | Specific IP queue updated | `ip` |
| `all_queues_updated` | All queues updated | - |

---

## 🎨 Advanced Usage

### Custom Configuration

**Change default port:**

```bash
uvicorn mock_openai_tool.backend.main:app --host 0.0.0.0 --port 9000
```

**Change request timeout:**

Edit `mock_openai_tool/backend/main.py` and modify the 300-second timeout value.

### Queue Persistence

Queue data is automatically saved to `preset_queues.json`, supporting backup and restore:

```bash
# Backup queue
cp preset_queues.json preset_queues.backup.json

# Restore queue
cp preset_queues.backup.json preset_queues.json
# Restart service
```

### Integration Testing Example

```python
import pytest
import requests

@pytest.fixture(scope="module")
def setup_queue():
    """Prepare response queue before tests"""
    test_responses = [
        {"id": "test-1", "choices": [{"message": {"content": "Answer 1"}}]},
        {"id": "test-2", "choices": [{"message": {"content": "Answer 2"}}]},
    ]
    requests.post(
        "http://localhost:8088/api/preset-queue/127.0.0.1/batch",
        json={"responses": test_responses, "status_code": 200}
    )
    yield
    requests.delete("http://localhost:8088/api/preset-queue/127.0.0.1")

def test_openai_integration(setup_queue):
    resp = requests.post(
        "http://localhost:8088/v1/chat/completions",
        json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Test"}]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "Answer 1"
```

---

## 🐳 Docker Deployment

### Basic Deployment

```bash
# Build image
docker build -t mock-openai-tool:latest .

# Run container with persistence
docker run -d \
  -p 8088:8000 \
  -v $(pwd)/preset_queues.json:/app/preset_queues.json \
  --name mock-openai-tool \
  mock-openai-tool:latest

# View logs
docker logs -f mock-openai-tool
```

---

## 🛠 Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Port already in use | Address already in use | `lsof -i :8000` to find and kill process, or use different port |
| WebSocket connection failed | Service not running or firewall blocking | Check service status, open port |
| Queue data lost | Not persisted | Use Docker `-v` to mount `preset_queues.json` |
| Request timeout | Manual mode 300s not responded | Respond promptly or use preset queue mode |

---

## 📊 Performance & Limits

### Performance Metrics

- **Concurrent connections**: Theoretically unlimited (limited by system resources)
- **Queue operations**: O(1) time complexity
- **Request timeout**: Default 300 seconds (configurable)
- **File import limit**: Maximum 10MB

### Resource Recommendations

| Environment | CPU | Memory | Notes |
|------------|-----|--------|-------|
| Development | 0.5 core | 512MB | Single user debugging |
| Testing | 1 core | 1GB | Small-scale testing |
| Production | 2 cores | 2GB | Concurrent testing |

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit Issues and Pull Requests.

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/mock-openai-tool.git
cd mock-openai-tool

# Install dependencies
pip install -r requirements.txt

# Start development server (with auto-reload)
uvicorn mock_openai_tool.backend.main:app --reload

# Run tests
pytest tests/
```

### Code Standards

- Follow PEP 8 Python code style
- Run tests before submitting
- Clear PR descriptions explaining changes

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🎯 Roadmap

- [ ] Support more OpenAI API endpoints (embeddings, images, etc.)
- [ ] Response latency simulation
- [ ] Request/response statistics and analysis
- [ ] Multi-user permission management
- [ ] Response template library
- [ ] Performance monitoring and metrics export

---

<div align="center">

**[⬆ Back to Top](#mock-openai-api-tool)**

Made with ❤️ by contributors

</div>
