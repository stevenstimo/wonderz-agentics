"""
GTM Platform configuratie — platform-specifieke context voor de GTM Agent.
Elke job die de GTM agent krijgt, bevat de platform context.
"""

GTM_PLATFORM_CONFIGS = {
    "wonderz": {
        "positioning": "The AI crew that gets things done",
        "target_audience": "Marketing managers, e-commerce founders, content teams (20-200 FTE)",
        "tone": "professioneel, B2B, resultaatgericht, geen jargon",
        "primary_channels": ["linkedin", "product_hunt", "developer_communities", "email"],
        "kpis": {
            "growth_mom": 0.15,        # 15% MoM
            "activation_rate_week1": 0.60,  # 60%
            "ltv_cac_ratio": 3.0,
            "k_factor_target": 0.8
        },
        "viral_mechanic": "Powered by Wonderz badge in gegenereerde content + referral credit",
        "content_formats": ["linkedin_carousel", "case_study", "demo_video", "email_sequence"],
        "avoid": ["consumer_tone", "too_technical", "feature_listing_without_benefit"]
    },
    "clawagency": {
        "positioning": "Your AI-powered e-commerce growth team",
        "target_audience": "Shopify/WooCommerce merchants €500k-€10M omzet",
        "tone": "ROI-gericht, direct, cijfer-gedreven, resultaat-focused",
        "primary_channels": ["linkedin_outreach", "cold_email", "case_studies", "ecom_forums"],
        "kpis": {
            "client_roi": 3.0,          # 300%
            "new_client_mom": 0.20,     # 20%
            "nps_target": 60,
            "k_factor_target": 0.5      # referral via klant success stories
        },
        "viral_mechanic": "Client success case studies + referral programma voor bestaande klanten",
        "content_formats": ["roi_calculator", "before_after_case_study", "linkedin_outreach", "webinar"],
        "avoid": ["vague_promises", "no_roi_data", "generic_agency_speak"]
    },
    "blogable": {
        "positioning": "SEO content that ranks + TikTok/Instagram repurposing in one click",
        "target_audience": "Content marketers, bloggers, kleine SEO bureaus",
        "tone": "creatief, inspirerend, praktisch, visueel",
        "primary_channels": ["tiktok", "instagram", "seo_organic", "youtube_shorts"],
        "kpis": {
            "dau_mau_ratio": 0.40,      # 40%
            "feature_adoption_social": 0.30,  # 30% blog→social adoptie
            "churn_monthly": 0.05,      # max 5%
            "k_factor_target": 1.2      # viraal via "Made with Blogable" watermark
        },
        "viral_mechanic": "Made with Blogable watermark + gratis tier met branding",
        "content_formats": ["tiktok_tutorial", "instagram_before_after", "seo_article", "youtube_short"],
        "avoid": ["b2b_corporate_tone", "text_heavy_social", "no_visual_hook"]
    }
}


def get_platform_context(platform: str) -> dict:
    """Haal platform-specifieke context op voor GTM Agent prompts."""
    config = GTM_PLATFORM_CONFIGS.get(platform)
    if not config:
        raise ValueError(
            f"Onbekend platform: {platform}. Kies uit: {list(GTM_PLATFORM_CONFIGS.keys())}"
        )
    return config
