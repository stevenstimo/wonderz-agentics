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
   Example: "Beste wielrennen fiets wielrennen Nederland wielrennen routes"
   
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
   "Salesteams besteden 40% van hun tijd aan administratie. Dit kost €30k per FTE per jaar. Ons platform automatiseert dit volledig."

2. **Statistic → Context → Our Approach**
   "73% van B2B leads converteert niet binnen 6 maanden. Wij verhogen dit naar 45% via automated nurturing."

3. **Question → Answer → Benefit**
   "Hoe verhoogt u leadkwaliteit zonder meer budget? Door alleen MQL-ready leads door te sturen naar sales."

### Body Patterns
Use this structure for features:
**Feature → Benefit → Use Case**

Example:
"Onze AI scoring engine (feature) verhoogt conversie met 28% (benefit). Klant X gebruikte dit om in Q3 2025 €2.4M extra omzet te genereren (use case)."

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
✅ Meer dan 500 B2B bedrijven vertrouwen op ons

### Avoid (Vague Claims)
❌ Aanzienlijke verbetering
❌ Veel voordelen
❌ Toonaangevend platform
❌ Revolutionaire oplossing
❌ Game-changer
❌ Cutting-edge technologie (zonder bewijs)

## Example Transformations

### BEFORE (Weak)
"Ons innovatieve platform helpt bedrijven beter presteren met geavanceerde features die resultaat leveren."

### AFTER (Strong)
"Automatiseer uw salesproces en verhoog conversie met 28%. Meer dan 500 B2B bedrijven vertrouwen op ons platform voor lead nurturing. Klant Acme Corp genereerde €800k extra ARR in Q4 2025."

## Verification Checklist
- [ ] Geen superlatieven zonder cijfermatig bewijs?
- [ ] Elke claim heeft data, testimonial of case study?
- [ ] CTA bevat concrete waarde-propositie?
- [ ] Taalgebruik consistent formeel (u/uw)?
- [ ] Minimaal 1 testimonial met bedrijfsnaam + functie?
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
- Gebruik contracties: "je''d", "we''ll", "dat''s"
- Korte zinnen: max 15-20 woorden
- Spreek lezer direct aan: "Stel je voor..."
- Gebruik vraagzinnen: "Herken je dit?"
- Voeg emoji toe waar passend (niet overdrijven) 😊
- Begin zinnen met "En" of "Maar" (casual mag dat)

### ❌ DON''T
- Corporate speak: "wij faciliteren", "optimaliseren van processen"
- Passieve constructies: "wordt gedaan" → gebruik "we doen"
- Lange paragrafen (max 3 zinnen)
- Te formeel: "derhalve", "bijgevolg", "teneinde"
- Overdreven enthousiasme: "AMAZING!!!", "SUPERVET!!!"

## Sentence Patterns

### Opening Hooks (Casual)
1. **Relatable Question**
   "Herken je dat? Je wilt sporten maar je agenda zit vol..."

2. **Personal Story Start**
   "Vorige week probeerde ik voor het eerst padel. Spoiler: ik won geen punt. 😅"

3. **Direct Address**
   "Luister, wielrennen is niet moeilijk. Je hebt een fiets, een weg, en wat lef nodig."

### Body Flow
Use short paragraphs (2-3 sentences) with breathing room.

**Pattern:**
Statement → Example → Takeaway

Example:
"Schaatsen leren is 80% vertrouwen, 20% techniek. (statement)

Ik zag vorige week een 5-jarige dit sneller oppakken dan een 30-jarige. Waarom? Hij dacht er niet over na. (example)

Moral: overthink het niet, gewoon doen. (takeaway)"

### Conversational Transitions
Replace formal transitions:
- Bovendien → Ook
- Derhalve → Dus
- Bijgevolg → Daarom
- Ten eerste → Eerst

## Example Transformations

### BEFORE (Too Formal)
"Wielrennen biedt aanzienlijke gezondheidsvoordelen. Onderzoek toont aan dat regelmatige training de cardiovasculaire conditie optimaliseert en het risico op chronische aandoeningen vermindert."

### AFTER (Casual)
"Wielrennen is gewoon goed voor je. Je hart wordt sterker, je conditie beter, en je voelt je fitter. Plus: je krijgt dat heerlijke na-sport gevoel. 💪"

## Emoji Guidelines
Use sparingly (1-2 per article max):
✅ After positive statements: "Dat lukte! 🎉"
✅ To emphasize emotion: "Echt waar? 😲"
❌ Not in every sentence
❌ Not multiple in one sentence

## Verification Checklist
- [ ] Gebruik je "je" ipv "u"?
- [ ] Korte paragrafen (max 3 zinnen)?
- [ ] Geen corporate speak?
- [ ] Leest het alsof je het hardop zou zeggen?
- [ ] Max 2 emoji in hele tekst?
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

### ✅ CORRECT
```
H1: Hoofdtitel (1x per pagina)
  H2: Main section
    H3: Subsection
    H3: Subsection
  H2: Main section
    H3: Subsection
```

### ❌ INCORRECT
```
H1: Titel
  H3: Subsection (H2 missing!)
  H2: Section (wrong order)
```

**Rule:** Nooit een heading level overslaan. H1 → H2 → H3, niet H1 → H3.

## Paragraph Length Guidelines

**Short-form content (blogs, articles):**
- Opening paragraph: 2-3 zinnen
- Body paragraphs: 3-4 zinnen max
- Conclusion: 2-3 zinnen

**Long-form content (guides, whitepapers):**
- Body paragraphs: 4-6 zinnen max
- Add whitespace every 100-150 words

**Rule:** Als een paragraaf >6 zinnen heeft, split het op.

## List Usage

### When to Use Bullet Lists
✅ 3+ items van gelijke waarde
✅ Non-sequential items (volgorde maakt niet uit)
✅ Quick scan items

Example:
"Wat heb je nodig voor wielrennen?
- Een fiets (duh)
- Een helm
- Comfortabele kleding
- Waterfles"

### When to Use Numbered Lists
✅ Sequential steps (volgorde belangrijk)
✅ Ranking/prioriteit
✅ Instructions

Example:
"Zo leer je schaatsen:
1. Zet helm en schaatsen aan
2. Loop eerst op het ijs (niet glijden)
3. Oefenen kleine glijbewegingen
4. Werk naar langere glijders"

### When NOT to Use Lists
❌ Alleen 2 items (gebruik "en" ipv lijst)
❌ Lange uitleg per item (gebruik H3 subsections)
❌ Narrative flow (gebruik prose)

## Opening Structure Pattern

**Hook → Context → Promise**

Example:
"Wielrennen lijkt intimiderend. (hook) Al die fancy fietsen, teams in Lycra, en jargon over "wattage" en "cadans". (context) Maar ik beloof je: binnen 2 weken fiets je met plezier. (promise)"

## Body Section Pattern

**Problem → Solution → Benefit**

Example:
"Beginners maken vaak deze fout: ze fietsen met te zwaar verzet. (problem) 

Gebruik een lichter verzet en draai sneller. (solution) 

Je benen blijven fris, je gaat sneller, en je geniet meer. (benefit)"

## Closing Structure Pattern

**Recap → CTA → Encouragement**

Example:
"Recap: lichte verzet, hoge cadans, bouw langzaam op. (recap)

Probeer het volgende rit. (CTA)

Je gaat het verschil merken, dat beloof ik. (encouragement)"

## Whitespace Rules

Add extra line break after:
- Every 2-3 paragraphs
- Before/after lists
- Before/after headings
- Before/after quotes or examples

**Rule:** Als een "wall of text" ontstaat (>200 woorden zonder break), voeg whitespace toe.

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

## Doel
Herken en vermijd deze veelvoorkomende fouten die content zwak maken.

## 🚫 Anti-Pattern 1: Vague Value Propositions

### FOUT
"Ons platform helpt bedrijven beter presteren met innovatieve oplossingen."

### WAAROM FOUT
- "Helpt" = te vaag
- "Beter presteren" = niet meetbaar
- "Innovatieve oplossingen" = betekenisloos buzzword

### FIX
"Ons platform verhoogt leadconversie met 28% via AI-scoring. Meer dan 500 B2B bedrijven gebruiken het."

**Regel:** Vervang elke vage claim met een cijfer of concreet voordeel.

---

## 🚫 Anti-Pattern 2: Feature Dumping

### FOUT
"Ons product heeft:
- Dashboard
- Rapportage
- Integraties
- Analytics
- Automatisering
- API access"

### WAAROM FOUT
Features zonder benefits = nutteloos
Lezer denkt: "En dan?"

### FIX
"Krijg automatische leadscoring (feature) zodat sales alleen met warme leads spreekt (benefit). Dit verhoogde conversie bij Acme Corp met 35% (social proof)."

**Regel:** Elke feature MOET een benefit + use case hebben.

---

## 🚫 Anti-Pattern 3: Passive Voice Overload

### FOUT
"De data wordt geanalyseerd en inzichten worden gegenereerd waarna rapporten worden gemaakt."

### WAAROM FOUT
Passieve stem = saai, indirect, zwak
Wie doet wat?

### FIX
"Wij analyseren uw data, genereren inzichten, en maken rapporten."

Of beter (actief + benefit):
"Ons platform analyseert data in realtime en waarschuwt u bij afwijkingen."

**Regel:** Zoek "wordt" en "worden" in je tekst. Herschrijf naar actieve stem.

---

## 🚫 Anti-Pattern 4: Wall of Text

### FOUT
Paragraaf van 10+ zinnen zonder witruimte, lijsten of subheadings. Lezer ziet een blok tekst en skipped het.

### WAAROM FOUT
Onleesbaar op mobile
Scanbaarheid = 0
Bounce rate omhoog

### FIX
- Split op in 2-3 zin paragrafen
- Voeg H2/H3 subsections toe
- Gebruik bullet lists voor 3+ items
- Voeg whitespace toe elke 150 woorden

**Regel:** Als een paragraaf >6 zinnen heeft, is het te lang.

---

## 🚫 Anti-Pattern 5: Jargon Without Context

### FOUT
"Onze SaaS platform biedt best-in-class ML-driven insights met seamless API integratie en omnichannel attribution modeling."

### WAAROM FOUT
Buzzword soup
Lezer denkt: "Wat betekent dit in normaal Nederlands?"

### FIX
"Ons online platform voorspelt welke leads kopen (ML = machine learning). Het werkt samen met uw CRM via API (= automatische datakoppeling)."

**Regel:** Als je jargon gebruikt, leg het uit in 1 zin. Of skip de jargon helemaal.

---

## 🚫 Anti-Pattern 6: Buried Lede

### FOUT
"In de moderne digitale economie waar bedrijven steeds meer data verzamelen en analyse belangrijker wordt voor competitief voordeel, biedt ons platform een oplossing die..."

(150 woorden later)

"...verhoogt conversie met 40%."

### WAAROM FOUT
Belangrijkste info staat onderaan
Lezer haakt af voor de payoff

### FIX
"Verhoog conversie met 40%. Zo werkt het: [uitleg]"

**Regel:** Lead met de belangrijkste info. Uitleg komt daarna.

---

## 🚫 Anti-Pattern 7: No Clear CTA

### FOUT
Article eindigt met:
"Hopelijk vond je dit nuttig. Tot de volgende keer!"

### WAAROM FOUT
Geen call-to-action
Lezer denkt: "Oké, en nu?"
Gemiste conversie-kans

### FIX
"Probeer het deze week:
→ Start met 1 route per week
→ Bouw langzaam af
→ Deel je voortgang in onze community [link]"

**Regel:** Elke content piece moet eindigen met een duidelijke volgende stap.

---

## 🚫 Anti-Pattern 8: Inconsistent Tone

### FOUT
Paragraaf 1: "Yo wielrenners! Dit ga je vet vinden..."
Paragraaf 3: "Derhalve dient men rekening te houden met de biomechanische aspecten..."

### WAAROM FOUT
Jarring shift = verwarrend
Lezer weet niet wat de vibe is

### FIX
Pick one tone en blijf consistent:
- Casual? Blijf casual
- Formeel? Blijf formeel
- Gebruik niet beide

**Regel:** Als je in paragraaf 1 "je" gebruikt, gebruik dan niet "u" in paragraaf 3.

---

## Verification Checklist
Run deze checks voor je content indient:

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
