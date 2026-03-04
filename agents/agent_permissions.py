"""Define allowed tool lists per agent module (MVP).

Add entries here when adding new agents.
"""

AGENT_ALLOWED_TOOLS = {
    # Copy agent: may read product and update product descriptions, but not update themes
    "copy_agent": [
        "shopify_admin_api.read_product",
        "shopify_admin_api.update_product",
    ],

    # Reviewer: only read operations and internal tools
    "reviewer_agent": [
        "shopify_admin_api.read_product",
        "nlp.sentiment_analyze",
    ],
}
