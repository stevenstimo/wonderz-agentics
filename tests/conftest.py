# Enable pytest-asyncio for async tests when running pytest without -p pytest_asyncio
def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as an asyncio test")
