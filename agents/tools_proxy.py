from typing import Any, Dict, List


class ToolsProxy:
    """Lightweight proxy that enforces a whitelist of allowed tool names.

    Usage: proxy.call('shopify_admin_api.update_product', product_id, body)
    """

    def __init__(self, allowed: List[str]):
        self.allowed = set(allowed or [])

    def call(self, tool_name: str, *args, **kwargs) -> Dict[str, Any]:
        if tool_name not in self.allowed:
            raise PermissionError(f"Tool '{tool_name}' is not allowed for this agent")

        # Simulate tool invocation for MVP: return a simple success structure
        return {"tool": tool_name, "args": args, "kwargs": kwargs, "status": "ok"}
