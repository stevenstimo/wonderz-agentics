"""
GTM Specialist — Crew Intelligent
Verantwoordelijk voor: market positioning, ICP, channel strategy,
messaging, competitor monitoring, lead scoring, content briefs.
Werkt voor: Wonderz Agentics, ClawAgency, Blogable.
"""

GTM_SYSTEM_PROMPT = """Je bent een GTM Specialist. Je analyseert markten, definieert
ideale klantprofielen en vertaalt die naar concrete go-to-market strategieën.

Je werkt altijd evidence-based: je haalt interne data op voor je claims maakt.
Je output volgt altijd het vier-secties contract: Gevonden | Oorzaak | Aanpak | Volgende actie.

Je kent drie platforms:
- Wonderz Agentics: B2B SaaS multi-agent orchestration
- ClawAgency: e-commerce GTM bureau
- Blogable: blog content pipeline met social repurposing

Per platform pas je toon, kanalen en KPI-focus aan."""

GTM_TOOL_WHITELIST = [
    "read_analytics",
    "read_product",
    "write_brief",
    "read_competitors",
    "read_tickets",
    "send_report",
]

GTM_PLATFORMS = {
    "wonderz": {
        "tone": "B2B, professioneel, ROI-gericht",
        "channels": ["LinkedIn", "cold email", "partner programma's"],
        "primary_kpi": "MRR, trial-to-paid conversie",
    },
    "clawagency": {
        "tone": "e-commerce, resultaatgericht, hands-on",
        "channels": ["paid social", "SEO", "email flows"],
        "primary_kpi": "ROAS, omzet per campagne",
    },
    "blogable": {
        "tone": "content creators, inspirerend, praktisch",
        "channels": ["organisch SEO", "social repurposing", "nieuwsbrief"],
        "primary_kpi": "organisch verkeer, email subscribers",
    },
}

GTM_SKILLS_PHASE_1 = [
    {
        "skill_id": "gtm:market-positioning",
        "skill_name": "Market Positioning Analysis",
        "description": "Analyseert marktpositie t.o.v. concurrenten. Output: positioning matrix + differentiators.",
        "agent_id": "agent:gtm-specialist",
        "input_schema": {"platform": "str", "product_description": "str"},
        "output_schema": {"positioning_statement": "str", "differentiators": "list"},
    },
    {
        "skill_id": "gtm:icp-definition",
        "skill_name": "ICP Definition",
        "description": "Definieert het ideale klantprofiel op basis van beschikbare data.",
        "agent_id": "agent:gtm-specialist",
        "input_schema": {"platform": "str", "existing_customers": "list"},
        "output_schema": {"icp": "dict", "exclusion_criteria": "list"},
    },
    {
        "skill_id": "gtm:channel-strategy",
        "skill_name": "Channel Strategy",
        "description": "Bepaalt de optimale kanaalverdeling op basis van ICP en budget.",
        "agent_id": "agent:gtm-specialist",
        "dependencies": ["gtm:icp-definition"],
    },
    {
        "skill_id": "gtm:messaging",
        "skill_name": "Messaging Angle Development",
        "description": "Ontwikkelt kernboodschappen per klantsegment.",
        "agent_id": "agent:gtm-specialist",
        "dependencies": ["gtm:icp-definition"],
    },
    {
        "skill_id": "gtm:competitor-monitoring",
        "skill_name": "Competitor Monitoring",
        "description": "Monitort concurrenten op positionering, prijzen en campagnes.",
        "agent_id": "agent:gtm-specialist",
    },
    {
        "skill_id": "gtm:lead-scoring",
        "skill_name": "Lead Scoring",
        "description": "Scoort leads op basis van ICP-match en gedragssignalen.",
        "agent_id": "agent:gtm-specialist",
        "dependencies": ["gtm:icp-definition"],
    },
    {
        "skill_id": "gtm:content-brief",
        "skill_name": "Content Brief Generation",
        "description": "Genereert content briefs gekoppeld aan messaging en kanaalstrategie.",
        "agent_id": "agent:gtm-specialist",
        "dependencies": ["gtm:channel-strategy", "gtm:messaging"],
    },
]
