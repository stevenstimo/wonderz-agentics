-- Skill 1: SEO Copywriting
INSERT INTO agent_skills (skill_id, name, domain, skill_type, applicable_to, content)
VALUES (
    'skill:copywriting:seo',
    'SEO Copywriting Best Practices',
    'copywriting',
    'technique',
    ARRAY['copywriter', 'seo', 'content-writer'],
    '# SEO Copywriting Best Practices

## Doel
Schrijf tekst die zowel menselijk leesbaar is als goed rankt in zoekmachines.

## Keyword Placement Rules

✅ DO:
- Primary keyword in eerste 100 woorden
- Keyword in H1 (exact match)
- Keyword natuurlijk 2-3x in body (gebruik LSI variants)
- Keyword in meta description (<160 chars)

❌ DON''T:
- Keyword stuffing (>5% density = spam flag)
- Exact match in elke zin (onnatuurlijk)
- Keyword in ALT text als niet relevant voor afbeelding

## Structuur Vereisten

✅ DO:
- Gebruik H1 → H2 → H3 hiërarchie (geen H3 zonder H2)
- Korte paragrafen: 2-3 zinnen max
- Bullet lists voor scanbaarheid
- Minimaal 2 interne links naar gerelateerde content

## Content Length Guidelines
- Blog post: 800-1200 woorden
- Product page: 300-500 woorden
- Landing page: 500-800 woorden
- Category page: 200-400 woorden

## Anti-Patterns to Avoid

🚫 "Keyword Salad" - Te veel keywords zonder context
   
🚫 "Thin Content" - <300 woorden voor commercial intent pages
   
🚫 "Duplicate Content" - Kopieer nooit van concurrenten, parafraseer altijd

## Verification Checklist
Before submitting, verify:
- [ ] Primary keyword in H1?
- [ ] Keyword density tussen 1-3%?
- [ ] Minimaal 300 woorden?
- [ ] H2/H3 subheadings aanwezig?
- [ ] Interne links naar min. 2 paginas?
- [ ] Meta description <160 tekens?

## Success Metrics
Track these after publication:
- Organic traffic increase: target +15% binnen 3 maanden
- Bounce rate: target <60%
- Average time on page: target >2 minuten
- SERP position: target top 10 voor primary keyword
'
) ON CONFLICT (skill_id) DO NOTHING;

-- Skill 2: B2B Professional Voice
INSERT INTO agent_skills (skill_id, name, domain, skill_type, applicable_to, content)
VALUES (
    'skill:voice:b2b-professional',
    'B2B Professional Voice & Tone',
    'voice',
    'voice',
    ARRAY['copywriter', 'email-writer', 'content-writer'],
    '# B2B Professional Voice & Tone

## Karakteristieken
- **Authoritative maar toegankelijk** - Expert zonder arrogant te zijn
- **Data-driven** - Elke claim met bewijs of statistiek
- **Action-oriented** - Elke paragraaf heeft een duidelijke takeaway
- **Formeel maar niet stijf** - "U" taalgebruik, geen onnodige jargon

## Sentence Construction

### Opening Patterns (Choose one per section)
1. **Problem → Agitate → Solution**
2. **Statistic → Context → Our Approach**
3. **Question → Answer → Benefit**

### Body Patterns
Use this structure for features:
**Feature → Benefit → Use Case**

### CTA Construction
Formula: **Action Verb + Value Proposition + Risk Removal**

✅ GOOD:
"Start gratis proefperiode — zie in 14 dagen hoe u 40% tijd bespaart. Geen creditcard vereist."

❌ BAD:
"Probeer het nu!" (te vaag, geen waarde)

## Word Choice Rules

### Use (Data-Driven)
✅ Verhoog conversie met 28%
✅ Bespaar 15 uur per week
✅ ROI +42% binnen 6 maanden

### Avoid (Vague Claims)
❌ Aanzienlijke verbetering
❌ Veel voordelen
❌ Toonaangevend platform
❌ Revolutionaire oplossing

## Verification Checklist
- [ ] Geen superlatieven zonder cijfermatig bewijs?
- [ ] Elke claim heeft data, testimonial of case study?
- [ ] CTA bevat concrete waarde-propositie?
- [ ] Taalgebruik consistent formeel (u/uw)?
- [ ] Geen jargon zonder uitleg?
'
) ON CONFLICT (skill_id) DO NOTHING;

-- Skill 3: Casual Conversational Tone
INSERT INTO agent_skills (skill_id, name, domain, skill_type, applicable_to, content)
VALUES (
    'skill:voice:casual-conversational',
    'Casual Conversational Writing',
    'voice',
    'voice',
    ARRAY['copywriter', 'content-writer', 'social-media'],
    '# Casual Conversational Writing

## Doel
Schrijf alsof je met een vriend praat - toegankelijk, vriendelijk, menselijk.

## Tone Karakteristieken
- **Persoonlijk** - Gebruik "je", spreek de lezer direct aan
- **Vriendelijk** - Warm zonder overdreven enthousiast
- **Natuurlijk** - Schrijf zoals je spreekt
- **Niet te formeel** - Geen "u" taalgebruik, geen corporate speak

## Do''s & Don''ts

### ✅ DO
- Korte zinnen: max 15-20 woorden
- Spreek lezer direct aan: "Stel je voor..."
- Gebruik vraagzinnen: "Herken je dit?"
- Begin zinnen met "En" of "Maar" (casual mag dat)

### ❌ DON''T
- Corporate speak: "wij faciliteren", "optimaliseren van processen"
- Passieve constructies: "wordt gedaan" → gebruik "we doen"
- Lange paragrafen (max 3 zinnen)
- Te formeel: "derhalve", "bijgevolg", "teneinde"

## Sentence Patterns

### Opening Hooks (Casual)
1. **Relatable Question** - "Herken je dat?"
2. **Personal Story Start** - "Vorige week probeerde ik..."
3. **Direct Address** - "Luister, dit is niet moeilijk."

### Conversational Transitions
Replace formal transitions:
- Bovendien → Ook
- Derhalve → Dus
- Bijgevolg → Daarom
- Ten eerste → Eerst

## Emoji Guidelines
Use sparingly (1-2 per article max):
✅ After positive statements
❌ Not in every sentence

## Verification Checklist
- [ ] Gebruik je "je" ipv "u"?
- [ ] Korte paragrafen (max 3 zinnen)?
- [ ] Geen corporate speak?
- [ ] Leest het alsof je het hardop zou zeggen?
- [ ] Begrijpelijk voor 16-jarige?
'
) ON CONFLICT (skill_id) DO NOTHING;

-- Skill 4: Content Structure Best Practices
INSERT INTO agent_skills (skill_id, name, domain, skill_type, applicable_to, content)
VALUES (
    'skill:structure:content-hierarchy',
    'Content Structure & Hierarchy',
    'structure',
    'technique',
    ARRAY['copywriter', 'content-writer', 'technical-writer'],
    '# Content Structure & Hierarchy

## Doel
Structureer content zodat het scanbaar, leesbaar en logisch is.

## Heading Hierarchy Rules
- Nooit een heading level overslaan. H1 → H2 → H3, niet H1 → H3.
- H1: 1x per pagina

## Paragraph Length Guidelines
**Short-form content:** 2-4 zinnen max per paragraaf
**Long-form content:** 4-6 zinnen max, whitespace elke 100-150 woorden
**Rule:** Als een paragraaf >6 zinnen heeft, split het op.

## List Usage
- Bullet lists: 3+ items van gelijke waarde, non-sequential
- Numbered lists: Sequential steps, ranking
- NIET voor slechts 2 items

## Opening Structure Pattern
**Hook → Context → Promise**

## Body Section Pattern
**Problem → Solution → Benefit**

## Closing Structure Pattern
**Recap → CTA → Encouragement**

## Whitespace Rules
Add extra line break after:
- Every 2-3 paragraphs
- Before/after lists
- Before/after headings

## Verification Checklist
- [ ] H1 → H2 → H3 hiërarchie correct?
- [ ] Geen paragrafen >6 zinnen?
- [ ] Lists gebruikt voor 3+ items?
- [ ] Whitespace na elke 2-3 paragrafen?
- [ ] Opening heeft hook + context + promise?
- [ ] Closing heeft recap + CTA?
'
) ON CONFLICT (skill_id) DO NOTHING;

-- Skill 5: Anti-Patterns (What NOT to Do)
INSERT INTO agent_skills (skill_id, name, domain, skill_type, applicable_to, content)
VALUES (
    'skill:anti-patterns:common-mistakes',
    'Common Writing Anti-Patterns',
    'quality',
    'anti-patterns',
    ARRAY['copywriter', 'reviewer', 'content-writer'],
    '# Common Writing Anti-Patterns

## 🚫 Anti-Pattern 1: Vague Value Propositions
FOUT: "Ons platform helpt bedrijven beter presteren."
FIX: Vervang elke vage claim met een cijfer of concreet voordeel.

## 🚫 Anti-Pattern 2: Feature Dumping
FOUT: Features zonder benefits.
FIX: Elke feature MOET een benefit + use case hebben.

## 🚫 Anti-Pattern 3: Passive Voice Overload
FOUT: "De data wordt geanalyseerd..."
FIX: Zoek "wordt" en "worden". Herschrijf naar actieve stem.

## 🚫 Anti-Pattern 4: Wall of Text
FOUT: Paragraaf van 10+ zinnen zonder witruimte.
FIX: Split op in 2-3 zin paragrafen, voeg H2/H3 en lists toe.

## 🚫 Anti-Pattern 5: Jargon Without Context
FOUT: Buzzword soup zonder uitleg.
FIX: Als je jargon gebruikt, leg het uit in 1 zin.

## 🚫 Anti-Pattern 6: Buried Lede
FOUT: Belangrijkste info staat onderaan.
FIX: Lead met de belangrijkste info. Uitleg komt daarna.

## 🚫 Anti-Pattern 7: No Clear CTA
FOUT: Content eindigt zonder call-to-action.
FIX: Elke content piece moet eindigen met een duidelijke volgende stap.

## 🚫 Anti-Pattern 8: Inconsistent Tone
FOUT: Mix van casual en formeel in dezelfde tekst.
FIX: Pick one tone en blijf consistent.

## Verification Checklist
- [ ] Geen vage claims zonder cijfers?
- [ ] Elke feature heeft een benefit?
- [ ] Geen passieve stem ("wordt", "worden")?
- [ ] Geen wall of text (max 6 zinnen per paragraaf)?
- [ ] Geen jargon zonder uitleg?
- [ ] Belangrijkste info staat bovenaan?
- [ ] Duidelijke CTA aan het einde?
- [ ] Consistente tone (casual OF formeel, niet beide)?
'
) ON CONFLICT (skill_id) DO NOTHING;
