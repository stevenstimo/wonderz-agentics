# Handoff voor Cursor (bovenaan plakken bij een doc-sync taak)

Het bijgewerkte document staat al klaar op:

**`docs/260320_CURSOR_jspdf_seo_first.md`** (in de project outputs / dit bestand als bron)

**Actie:** kopieer de inhoud van dat bestand naar de repo op **dezelfde locatie** (`docs/260320_CURSOR_jspdf_seo_first.md`).

- Geen codewijzigingen.
- Geen commit tenzij apart gevraagd.

Cursor doet **alleen** de doc-update, niets anders. Daarna volgt de volledige specificatie hieronder.

---

# 260320 — jspdf CVE fix + SEO-first volgorde

**Versie:** 1.1  
**Datum:** 20 maart 2026  
**Scope:** Twee onafhankelijke items, één commit (implementatie); dit document beschrijft opdracht + beslisregels.

---

## Beslisregels voor Cursor (voor uitvoering)

**Item A (jspdf)**  
- Cursor kiest zelf tussen **Optie 1 — `window.print()`** (geen dependency) en **Optie 2 — `@react-pdf/renderer`** (minimaal, alleen als print de layout/functioneel niet haalbaar maakt).  
- **Standaardvoorkeur = Optie 1 (print)** — minste impact op de codebase.  
- **Volledige PDF v2** (pixel-perfect / grote rebuild) blijft **uitgesteld tot na de TanStack Query-migratie**.

**Item B (SEO-first)**  
- Eerst **pre-flight** uitvoeren (bash-blokken verderop).  
- Op basis van die output het pad kiezen:  
  - **Pad 1 — SEO-agent zit al in de pipeline** (bijv. `seo` in agent-runner / plannen / `job_steps`): voeg **alleen** de **HandoffContext**-koppeling toe (keywords door naar copywriter); geen dubbele SEO-laag.  
  - **Pad 2 — geen SEO-stap in de uitvoeringsvolgorde:** voeg een **minimale** SEO-stap vóór de copywriter toe (zelfde aanroeppatroon als bestaande agents), **zonder** nieuwe tool-integraties (geen GSC in deze stap).  
- Details en voorbeeldvelden staan in **B.2** en **B.3**.

---

## Context

**Item A (jspdf):** jspdf 4.2.0 heeft 1 Critical en 1 High CVE. De volledige PDF v2 rebuild (naar `@react-pdf/renderer`) is uitgesteld tot na de TanStack Query migratie. De opdracht hier is dus: jspdf verwijderen en vervangen door een minimale, veilige oplossing die de bestaande exportfunctionaliteit intact houdt.

**Item B (SEO-first):** De huidige pipeline stuurt de copywriter aan zonder dat die de SEO keywords als input krijgt. De gewenste volgorde is: SEO keyword plan genereren eerst, dan de copywriter aansturen met die keywords als `HandoffContext`.

---

## Pre-flight

```bash
# 1. jspdf locaties vinden
grep -rn "jspdf\|html2canvas\|jsPDF" web_ui/frontend/src --include="*.jsx" --include="*.js" --include="*.ts"

# 2. package.json checken
cat web_ui/frontend/package.json | grep -E "jspdf|html2canvas"

# 3. SEO pipeline locatie vinden
grep -rn "seo\|keyword\|HandoffContext\|copywriter" app/ --include="*.py" | grep -iv "test\|spec" | head -30

# 4. Hoe wordt een job momenteel aangestuurd vanuit SEO naar copywriter?
grep -rn "handoff\|next_agent\|copywriter\|seo_keywords" app/orchestration/ --include="*.py" | head -20
```

Rapporteer de output. Dan pas uitvoeren.

---

## Item A — jspdf vervangen (CVE fix)

### A.1 Strategie

Geen volledige PDF v2 rebuild (dat is na TanStack). Wel: jspdf en html2canvas volledig verwijderen en vervangen door een van de twee opties hieronder. **Na pre-flight:** export beoordelen; **bij twijfel Optie 1 (print).** Cursor kiest de optie die het minste raakt aan de bestaande code.

**Optie 1 — Browser print (voorkeur als de export simpel is):**
Vervang de jspdf export door `window.print()` met een print-specifieke CSS class die de relevante content zichtbaar maakt en de rest verbergt. Geen dependency nodig.

```jsx
// Oud
import jsPDF from 'jspdf';
const doc = new jsPDF();
doc.html(element, { callback: (doc) => doc.save('export.pdf') });

// Nieuw
const handleExport = () => {
  window.print();
};
```

Print CSS toevoegen aan de stylesheet:
```css
@media print {
  .no-print { display: none !important; }
  .print-only { display: block !important; }
}
```

**Optie 2 — @react-pdf/renderer (als de layout complexer is):**
Alleen gebruiken als Optie 1 de bestaande layout niet kan reproduceren. Installeer minimaal:

```bash
npm install @react-pdf/renderer
```

Bouw een minimale `<PDFExport>` component die de essentiële data (naam, metrics, datum) als simpel PDF-document exporteert. Geen pixel-perfect replica van de huidige layout — dat is de v2 taak.

### A.2 Uitvoering

1. Identificeer welk component de jspdf export gebruikt (vermoedelijk `ClientDashboard.jsx` of vergelijkbaar).
2. Bepaal of de export simpel genoeg is voor Optie 1. Zo ja: gebruik Optie 1.
3. Vervang de implementatie.
4. Verwijder jspdf en html2canvas uit `package.json`:
   ```bash
   npm uninstall jspdf html2canvas
   ```
5. Verifieer dat `npm run build` slaagt.

### A.3 Acceptatiecriteria

- [ ] jspdf en html2canvas niet meer aanwezig in `package.json`
- [ ] `npm audit` toont de eerder gevonden Critical/High CVE niet meer
- [ ] Export knop werkt nog steeds (browser print dialog of PDF download)
- [ ] `npm run build` slaagt zonder errors
- [ ] Geen `import jsPDF` of `import html2canvas` meer in de codebase

---

## Item B — SEO-first volgorde in de pipeline

### B.1 Gewenste volgorde

```
Gebruiker start job
    ↓
CEO intake + plan
    ↓
SEO specialist → genereert keyword plan (focus keywords, zoekvolume, intent)
    ↓
HandoffContext: keywords meegeven aan volgende agent
    ↓
Copywriter → schrijft content MET keywords als input
    ↓
Reviewer → beoordeelt
```

### B.2 Wat er moet veranderen

Zie eerst **Beslisregels voor Cursor** (Pad 1 vs Pad 2 na pre-flight).

Zoek hoe de pipeline momenteel de volgorde van agents bepaalt. Kijk specifiek naar:
- Hoe `determine_next_step` of de NEXUS pipeline de agent-volgorde bepaalt
- Of er al een SEO agent in de pipeline zit
- Hoe `HandoffContext` of een equivalent nu werkt

**Als er al een SEO agent bestaat in de pipeline:**

Zorg dat de output van de SEO agent wordt doorgegeven als input aan de copywriter. Concreet:

```python
# In de HandoffContext of job context update na SEO stap:
context.update({
    "seo_keywords": seo_result.get("keywords", []),
    "focus_keyword": seo_result.get("focus_keyword", ""),
    "keyword_intent": seo_result.get("intent", ""),
})
```

En in de copywriter system prompt of taak-instructie:

```python
# Voeg toe aan de copywriter prompt als seo_keywords aanwezig zijn in context:
if context.get("seo_keywords"):
    seo_instruction = f"""
## SEO Instructies
Verwerk de volgende keywords natuurlijk in de tekst:
- Focus keyword: {context['focus_keyword']}
- Aanvullende keywords: {', '.join(context['seo_keywords'])}
- Zoekintentie: {context.get('keyword_intent', 'informatief')}

Het focus keyword moet voorkomen in de eerste alinea en minimaal 2x in de volledige tekst.
"""
```

**Als er nog geen SEO agent in de pipeline zit:**

Voeg de SEO stap toe vóór de copywriter in `determine_next_step` of het NEXUS pipeline configuratiebestand. Minimale SEO stap:

```python
async def run_seo_step(job_id: str, context: dict, db_pool) -> dict:
    """
    Genereert een basis keyword plan op basis van het job onderwerp.
    Output wordt als HandoffContext meegegeven aan de copywriter.
    """
    # Gebruik de bestaande Claude API aanroep patroon uit de codebase
    # Prompt: geef 1 focus keyword + 3-5 aanvullende keywords terug als JSON
    # Sla op in context: seo_keywords, focus_keyword, keyword_intent
```

### B.3 Regels

- Gebruik het bestaande patroon voor agent-aanroepen in de codebase — geen nieuwe abstracties
- Als de SEO agent al bestaat: alleen de HandoffContext koppeling toevoegen
- Als die niet bestaat: minimale implementatie, geen volledige SEO agent met alle features
- De copywriter mag de SEO instructies alleen krijgen als `seo_keywords` aanwezig is in de context (geen breaking change voor jobs zonder SEO stap)

### B.4 Acceptatiecriteria

- [ ] Bij een nieuwe job doorloopt de pipeline SEO stap vóór de copywriter
- [ ] De copywriter ontvangt `seo_keywords` en `focus_keyword` als context
- [ ] De gegenereerde tekst bevat aantoonbaar het focus keyword
- [ ] Bestaande jobs zonder SEO context breken niet (graceful fallback)
- [ ] Geen console errors of backend exceptions in de worker logs

---

## Wat je NIET doet

- Geen volledige PDF v2 rebuild — dat is een aparte taak na TanStack
- Geen nieuwe SEO tool integraties (geen GSC aanroepen in deze stap)
- Geen wijzigingen aan de database schema
- Geen `git add -A`

---

## Commit

```bash
# Stage exact de bestanden die zijn aangepast
git add web_ui/frontend/package.json
git add web_ui/frontend/package-lock.json
git add web_ui/frontend/src/<component met jspdf>.jsx
git add web_ui/frontend/src/index.css                    # als print CSS toegevoegd
git add app/orchestration/<pipeline bestand>.py          # of nexus_pipeline.py
git add app/services/<seo of copywriter bestand>.py      # als aangepast

git commit -m "fix: vervang jspdf (CVE) door browser print; feat(pipeline): SEO-first volgorde met keyword HandoffContext"
```

Daarna deployen:

```bash
sudo systemctl restart wonderz-backend
cd web_ui/frontend && npm run build
```

---

## Acceptatiecriteria totaalcheck

- [ ] `npm audit` — Critical/High CVE van jspdf niet meer aanwezig
- [ ] Export werkt nog steeds
- [ ] Pipeline doorloopt SEO stap vóór copywriter bij nieuwe job
- [ ] Copywriter output bevat focus keyword
- [ ] `npm run build` slaagt
- [ ] `journalctl -u crew-worker -f` toont geen nieuwe errors na deploy
