# Google Integrations registry
from app.integrations.google_crux import ENABLED as CRUX_ENABLED
from app.integrations.google_crux import fetch_crux
from app.integrations.google_indexing import ENABLED as INDEXING_ENABLED
from app.integrations.google_indexing import request_indexing
from app.integrations.google_knowledge_graph import ENABLED as KG_ENABLED
from app.integrations.google_knowledge_graph import search_entity
from app.integrations.google_natural_language import ENABLED as NL_ENABLED
from app.integrations.google_natural_language import full_analysis as nl_analyze
from app.integrations.google_pagespeed import ENABLED as PAGESPEED_ENABLED
from app.integrations.google_pagespeed import fetch_pagespeed
from app.integrations.google_translate import ENABLED as TRANSLATE_ENABLED
from app.integrations.google_translate import translate

GOOGLE_INTEGRATIONS_STATUS = {
    "pagespeed": PAGESPEED_ENABLED,
    "crux": CRUX_ENABLED,
    "natural_language": NL_ENABLED,
    "indexing": INDEXING_ENABLED,
    "knowledge_graph": KG_ENABLED,
    "translate": TRANSLATE_ENABLED,
    "business_profile": None,
    "youtube": None,
    "merchant_center": None,
    "sheets": None,
}
