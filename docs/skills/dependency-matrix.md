# Skills Library — Dependency Matrix

Master index for skill dependencies. **Update this file with every skill change.**

---

## Task Type → Primary & Supporting Skills

| Task Type | Primary Skill | Supporting Skills |
|-----------|---------------|-------------------|
| Full GTM strategy for new market | skill:gtm:strategy-commercial-v2 | skill:gtm:paid-media-v1 + skill:gtm:ymyl-compliance-v1 + skill:gtm:b2b2c-distribution-v1 + skill:gtm:market-sizing-tam-v1 + skill:gtm:positioning-statement-v1 + skill:gtm:channel-selection-entry-v1 + skill:gtm:launch-sequencing-v1 |
| Market entry regulated industry | skill:gtm:regulatory-screening-v1 | skill:gtm:ymyl-compliance-v1 + skill:gtm:strategy-commercial-v2 + skill:gtm:launch-sequencing-v1 |
| Market sizing / validation | skill:gtm:market-sizing-tam-v1 | research-brief-synthesis + competitive-keyword-gap-analysis |
| Competitive positioning | skill:gtm:positioning-statement-v1 | skill:gtm:strategy-commercial-v2 + skill:gtm:market-sizing-tam-v1 |
| Channel strategy | skill:gtm:channel-selection-entry-v1 | skill:gtm:strategy-commercial-v2 + skill:gtm:paid-media-v1 + skill:gtm:b2b2c-distribution-v1 |
| Launch planning | skill:gtm:launch-sequencing-v1 | skill:gtm:channel-selection-entry-v1 + skill:gtm:ymyl-compliance-v1 + skill:gtm:paid-media-v1 |

---

## Active Skills

| skill_id | Name | Version | Status |
|----------|------|---------|--------|
| skill:gtm:strategy-commercial-v2 | GTM Strategy Framework — Commercial Edition | 2.0 | Active |
| skill:gtm:paid-media-v1 | Paid Media Strategy for GTM | 1.0 | Active |
| skill:gtm:ymyl-compliance-v1 | YMYL Compliance & E-E-A-T in Regulated Markets | 1.0 | Active |
| skill:gtm:b2b2c-distribution-v1 | B2B2C Partnership & Distribution Strategy | 1.0 | Active |
| skill:seo:strategy-realistic-v2 | SEO Strategy — Realistic Market Edition | 2.0 | Active |
| skill:content:strategy-lifecycle-v2 | Content Strategy — Distribution & Lifecycle Edition | 2.0 | Active |
| skill:gtm:market-sizing-tam-v1 | Market Sizing (TAM/SAM/SOM) | 1.0 | Active |
| skill:gtm:positioning-statement-v1 | Positioning Statement Framework | 1.0 | Active |
| skill:gtm:channel-selection-entry-v1 | Channel Selection for Market Entry | 1.0 | Active |
| skill:gtm:launch-sequencing-v1 | Launch Sequencing | 1.0 | Active |
| skill:gtm:regulatory-screening-v1 | Regulatory Screening for Market Entry | 1.0 | Active |

---

## Known Backlog

- Retention & Renewal Strategy (lifecycle layer, not yet formalized as standalone skill)
- Competitive Intelligence Framework (AdSpy integration points)
- Pricing Strategy for Digital Products (unit economics companion skill)

---

## Dependency Rules

When adding or upgrading a skill:

1. **Check dependencies:** Does this skill depend on any existing skills? Add to table below.
2. **Check dependents:** Do any existing skills now depend on this new skill? Update those skills.
3. **Flag missing:** If a dependency does not yet exist, mark as `[PENDING: skill_id]` and add to backlog.

---

## Skill Dependencies (skill | REQUIRED / CONDITIONAL / OPTIONAL)

| Skill | Depends On | Type |
|-------|------------|------|
| skill:gtm:strategy-commercial-v2 | skill:gtm:market-sizing-tam-v1, skill:gtm:positioning-statement-v1 | CONDITIONAL |
| skill:gtm:regulatory-screening-v1 | skill:gtm:ymyl-compliance-v1 | REQUIRED |
| skill:gtm:launch-sequencing-v1 | skill:gtm:channel-selection-entry-v1, skill:gtm:ymyl-compliance-v1 | REQUIRED |
| *(Add rows as skills are created or updated)* | | |
