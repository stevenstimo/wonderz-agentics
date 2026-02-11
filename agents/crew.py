from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field


@dataclass
class AgentSpec:
    name: str
    role: str
    goal: str
    backstory: str
    tools: List[str]
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]


# ---------- Base IO models ----------
class BaseInput(BaseModel):
    job_id: Optional[str]
    store_id: Optional[str]
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BaseOutput(BaseModel):
    status: str = "success"
    summary: Optional[str]
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)


# ---------- Agent-specific schemas & specs ----------

# 1) Shopify Developer: Focus on Liquid/API
class ShopifyDeveloperInput(BaseInput):
    product_id: Optional[str]
    change_request: Optional[str]
    target_templates: Optional[List[str]] = None


class ShopifyDeveloperOutput(BaseOutput):
    code_snippets: Optional[Dict[str, str]] = None
    api_calls: Optional[List[Dict[str, Any]]] = None
    migration_steps: Optional[List[str]] = None


ShopifyDeveloper = AgentSpec(
    name="shopify_developer",
    role="Shopify Developer",
    goal="Implement template and API changes (Liquid, storefront/admin API) per request.",
    backstory=(
        "Experienced Shopify developer: converts product/UX requirements into Liquid templates, API calls, and small integration glue code."
    ),
    tools=[
        "shopify_admin_api.read_product",
        "shopify_admin_api.update_theme",
        "shopify_admin_api.create_script_tag",
        "code_formatter.format_snippet",
    ],
    input_model=ShopifyDeveloperInput,
    output_model=ShopifyDeveloperOutput,
)


# 2) SEO Specialist
class SEOSpecialistInput(BaseInput):
    page_path: Optional[str]
    existing_meta: Optional[Dict[str, str]]
    keywords_seed: Optional[List[str]]


class SEOSpecialistOutput(BaseOutput):
    title: Optional[str]
    meta_description: Optional[str]
    suggested_keywords: Optional[List[str]]
    structured_meta: Optional[Dict[str, Any]]


SEOSpecialist = AgentSpec(
    name="seo_specialist",
    role="SEO Specialist",
    goal="Produce SEO-optimized titles, meta descriptions and prioritized keywords for storefront pages.",
    backstory=("Focuses on on-page SEO, structured data and merchant search intent for commerce sites."),
    tools=["seo.analyze_text", "shopify_admin_api.read_product", "keyword_tool.suggest"],
    input_model=SEOSpecialistInput,
    output_model=SEOSpecialistOutput,
)


# 3) Product Manager (catalog structure)
class ProductManagerInput(BaseInput):
    catalog_snapshot: Optional[Dict[str, Any]]
    business_goals: Optional[Dict[str, Any]]


class ProductManagerOutput(BaseOutput):
    category_schema: Optional[Dict[str, Any]]
    product_attribute_spec: Optional[Dict[str, Any]]
    migration_plan: Optional[List[Dict[str, Any]]]


ProductManager = AgentSpec(
    name="product_manager",
    role="Product Manager",
    goal="Design a scalable catalog taxonomy and attribute schema aligned with business goals.",
    backstory=("Prior experience designing product taxonomies for mid-size stores; balances discovery with implementation constraints."),
    tools=["shopify_admin_api.list_collections", "data_schema.validate", "catalog_migration.plan"],
    input_model=ProductManagerInput,
    output_model=ProductManagerOutput,
)


# 4) Advertising Expert
class AdvertisingExpertInput(BaseInput):
    target_audience: Optional[Dict[str, Any]]
    product_brief: Optional[Dict[str, Any]]
    performance_goals: Optional[Dict[str, Any]]


class AdvertisingExpertOutput(BaseOutput):
    ad_copies: Optional[List[Dict[str, Any]]]
    creative_briefs: Optional[List[Dict[str, Any]]]
    budget_split: Optional[Dict[str, float]]
    roas_prediction: Optional[Dict[str, Any]]


AdvertisingExpert = AgentSpec(
    name="advertising_expert",
    role="Advertising Expert",
    goal="Create ad-copy, campaign structure and ROAS estimates for paid channels.",
    backstory=("Hands-on performance marketer with experience across Facebook, Google and feed-based shopping ads."),
    tools=["ads_generator.generate_copy", "ads_simulator.estimate_roas", "audience_tool.segment"],
    input_model=AdvertisingExpertInput,
    output_model=AdvertisingExpertOutput,
)


# 5) CX Agent (support/FAQ)
class CXAgentInput(BaseInput):
    sample_tickets: Optional[List[Dict[str, Any]]]
    product_info: Optional[Dict[str, Any]]


class CXAgentOutput(BaseOutput):
    faq_items: Optional[List[Dict[str, str]]]
    canned_responses: Optional[List[Dict[str, str]]]
    escalation_guidelines: Optional[List[str]]


CXAgent = AgentSpec(
    name="cx_agent",
    role="CX Agent",
    goal="Surface common support questions, provide canonical answers and escalation rules.",
    backstory=("Customer support lead who writes concise, empathy-first responses and organizes self-service content."),
    tools=["support.search_tickets", "knowledge_base.create_article", "shopify_admin_api.read_order"],
    input_model=CXAgentInput,
    output_model=CXAgentOutput,
)


# 6) Data Analyst (GA4/Shopify analytics)
class DataAnalystInput(BaseInput):
    date_range: Optional[Dict[str, str]]
    metrics: Optional[List[str]]
    segment: Optional[Dict[str, Any]]


class DataAnalystOutput(BaseOutput):
    key_metrics: Optional[Dict[str, Any]]
    anomalies: Optional[List[Dict[str, Any]]]
    recommended_reports: Optional[List[Dict[str, Any]]]


DataAnalyst = AgentSpec(
    name="data_analyst",
    role="Data Analyst",
    goal="Produce actionable analytics insights combining GA4 and Shopify data to inform next steps.",
    backstory=("Uses event-level GA4 data and Shopify orders to compute funnel metrics and spot anomalies."),
    tools=["ga4.query", "shopify_reports.orders_summary", "data_viz.plot"],
    input_model=DataAnalystInput,
    output_model=DataAnalystOutput,
)


# 7) CRO Expert (conversion hypotheses)
class CROExpertInput(BaseInput):
    current_conversion_rates: Optional[Dict[str, float]]
    page_variants: Optional[List[Dict[str, Any]]]


class CROExpertOutput(BaseOutput):
    hypotheses: Optional[List[Dict[str, Any]]]
    priority: Optional[List[str]]
    experiment_designs: Optional[List[Dict[str, Any]]]


CROExpert = AgentSpec(
    name="cro_expert",
    role="CRO Expert",
    goal="Generate prioritized conversion optimization hypotheses and experimental designs.",
    backstory=("Conversion optimizer who writes testable hypotheses and lightweight A/B experiment plans."),
    tools=["analytics.fetch_conversion", "ab_test.plan", "ux_review.suggest_changes"],
    input_model=CROExpertInput,
    output_model=CROExpertOutput,
)


# 8) Logistics Agent
class LogisticsAgentInput(BaseInput):
    inventory_snapshot: Optional[Dict[str, Any]]
    supplier_lead_times: Optional[List[Dict[str, Any]]]


class LogisticsAgentOutput(BaseOutput):
    restock_plan: Optional[Dict[str, Any]]
    supply_risks: Optional[List[Dict[str, Any]]]
    fulfilment_tips: Optional[List[str]]


LogisticsAgent = AgentSpec(
    name="logistics_agent",
    role="Logistics Agent",
    goal="Assess supply chain constraints and produce restock plans and risk mitigations.",
    backstory=("Works with inventory and supplier data to reduce stockouts and optimize reorder points."),
    tools=["inventory.fetch_levels", "supplier_api.get_lead_times", "forecasting.forecast_demand"],
    input_model=LogisticsAgentInput,
    output_model=LogisticsAgentOutput,
)


# 9) Legal Agent (AVG/Compliance)
class LegalAgentInput(BaseInput):
    data_processing_uses: Optional[List[Dict[str, Any]]]
    store_region: Optional[str]


class LegalAgentOutput(BaseOutput):
    compliance_summary: Optional[Dict[str, Any]]
    required_actions: Optional[List[Dict[str, Any]]]
    privacy_text_snippets: Optional[Dict[str, str]]


LegalAgent = AgentSpec(
    name="legal_agent",
    role="Legal Agent",
    goal="Identify GDPR/AVG risks and propose concrete compliance actions and privacy text snippets.",
    backstory=("Legal reviewer with privacy and e-commerce compliance experience; outputs audit-friendly findings."),
    tools=["legal.db_search", "privacy_text.generate", "compliance.checklist"],
    input_model=LegalAgentInput,
    output_model=LegalAgentOutput,
)


# Registry
AGENTS: Dict[str, AgentSpec] = {
    ShopifyDeveloper.name: ShopifyDeveloper,
    SEOSpecialist.name: SEOSpecialist,
    ProductManager.name: ProductManager,
    AdvertisingExpert.name: AdvertisingExpert,
    CXAgent.name: CXAgent,
    DataAnalyst.name: DataAnalyst,
    CROExpert.name: CROExpert,
    LogisticsAgent.name: LogisticsAgent,
    LegalAgent.name: LegalAgent,
}


def get_agent(name: str) -> Optional[AgentSpec]:
    return AGENTS.get(name)
