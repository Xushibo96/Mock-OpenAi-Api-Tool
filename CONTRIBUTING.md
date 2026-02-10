# Contributing to Mock OpenAI Tool

Thank you for your interest in contributing to Mock OpenAI Tool! We welcome contributions from the community.

## How to Contribute

### Reporting Issues

If you find a bug or have a feature request:

1. Check if the issue already exists in the [GitHub Issues](https://github.com/yourusername/mock-openai-tool/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Your environment details (OS, Python version, etc.)

### Submitting Changes

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/mock-openai-tool.git
   cd mock-openai-tool
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Write clean, readable code
   - Follow PEP 8 style guide for Python code
   - Add tests for new features
   - Update documentation as needed

4. **Test your changes**
   ```bash
   # Run all tests
   pytest tests/

   # Run specific test file
   pytest tests/test_queue_manager.py
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   Use conventional commit messages:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `test:` for test additions/changes
   - `refactor:` for code refactoring
   - `chore:` for maintenance tasks

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your feature branch
   - Fill in the PR template with:
     - Description of changes
     - Related issue numbers
     - Testing performed
     - Screenshots (if UI changes)

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip package manager
- Git

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Install development dependencies (if any)
pip install pytest pytest-asyncio httpx

# Run the development server with auto-reload
uvicorn mock_openai_tool.backend.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v
```

## Code Standards

### Python Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and small (< 50 lines)
- Use type hints where appropriate

### Example

```python
from typing import Dict, List, Optional

async def get_queue_items(ip: str) -> List[Dict]:
    """
    Get all queue items for a specific IP address.

    Args:
        ip: The IP address to query

    Returns:
        List of queue items with response data

    Raises:
        ValueError: If IP address is invalid
    """
    # Implementation here
    pass
```

### Testing

- Write unit tests for new functions
- Use pytest fixtures for common setup
- Test both success and error cases
- Aim for high code coverage

### Documentation

- Update README.md if adding new features
- Add inline comments for complex logic
- Update API documentation for new endpoints
- Include usage examples

## Project Structure

```
mock-openai-tool/
├── mock_openai_tool/
│   ├── backend/
│   │   ├── main.py           # FastAPI application
│   │   ├── api_routes.py     # REST API endpoints
│   │   ├── queue_manager.py  # Queue management logic
│   │   └── preset_validator.py  # JSON validation
│   └── frontend/
│       ├── index.html        # Web interface
│       └── style.css         # Styling
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_api.py          # API endpoint tests
│   └── test_queue_manager.py # Queue manager tests
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker configuration
└── README.md               # Project documentation
```

## Areas for Contribution

We especially welcome contributions in these areas:

- 🐛 **Bug fixes** - Fix reported issues
- ✨ **New features** - Implement items from the roadmap
- 📚 **Documentation** - Improve guides and examples
- 🧪 **Tests** - Increase test coverage
- 🎨 **UI/UX** - Enhance the web interface
- 🔧 **Performance** - Optimize existing code

## Questions?

If you have questions about contributing:

- Open a [GitHub Discussion](https://github.com/yourusername/mock-openai-tool/discussions)
- Comment on relevant issues
- Review existing documentation

## License

By contributing to Mock OpenAI Tool, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing! 🎉
