# MCP-plugins overzicht

Korte referentie voor alle MCP-servers in dit project: wanneer te gebruiken en auth-status.

---

## 1. Supabase  
**Server:** `plugin-supabase-supabase` | **Naam:** supabase  

**Gebruik:** Database queries, tabelbeheer, migraties. Proactief inzetten wanneer een taak database/Supabase raakt.

**Auth:** Token in `.cursor/mcp.json` (PAT, geen OAuth). Zie [MCP_SUPABASE.md](.cursor/MCP_SUPABASE.md).

---

## 2. Stripe  
**Server:** `plugin-stripe-stripe` | **Naam:** stripe  

**Gebruik:** Stripe-integratie (betalingen, subscriptions, etc.). Onder “Plugins beschikbaar” in .cursorrules.

**Auth:** Vereist `mcp_auth`. In Cursor: wanneer de Stripe MCP om auth vraagt, de flow volgen (browser/login).

---

## 3. Slack  
**Server:** `plugin-slack-slack` | **Naam:** slack  

**Gebruik:** Teamnotificaties bij deploys of kritieke fouten.

**Auth:** Vereist `mcp_auth`. Auth-flow in Cursor volgen wanneer Slack MCP daarom vraagt.

---

## 4. Linear  
**Server:** `plugin-linear-linear` | **Naam:** linear  

**Gebruik:** Issue aanmaken bij bugs of feature requests.

**Auth:** Vereist `mcp_auth`. Auth-flow in Cursor volgen wanneer Linear MCP daarom vraagt.

---

## 5. Sentry  
**Server:** `plugin-sentry-sentry` | **Naam:** sentry  

**Gebruik:** Foutmonitoring en error tracking. Onder “Plugins beschikbaar” in .cursorrules.

**Auth:** Vereist `mcp_auth`. Auth-flow in Cursor volgen wanneer Sentry MCP daarom vraagt.

---

## 6. Neon Postgres  
**Server:** `plugin-neon-postgres-neon` | **Naam:** neon  

**Gebruik:** Alternatieve DB-operaties indien relevant (Postgres, o.a. serverless).

**Auth:** Vereist `mcp_auth`. Auth-flow in Cursor volgen wanneer Neon MCP daarom vraagt.

---

## 7. Context7 (twee varianten)  
**Servers:** `plugin-context7-plugin-context7` / `plugin-compound-engineering-context7` | **Naam:** context7  

**Gebruik:** Documentatie opzoeken voor gebruikte libraries. Inzetten bij setupvragen, API-referenties of codevoorbeelden.

**Tools:**  
- `resolve-library-id`: package/productnaam omzetten naar Context7 library-ID.  
- `query-docs`: actuele documentatie en codevoorbeelden ophalen voor een library/framework (na resolve).

**Auth:** Geen auth nodig; tools direct beschikbaar.

---

## 8. cursor-ide-browser  
**Server:** `cursor-ide-browser` | **Naam:** cursor-ide-browser  

**Gebruik:** Web navigeren en met de pagina interacteren. Voor frontend/webapp-ontwikkeling en het testen van code.

**Workflow:** `browser_navigate` → `browser_lock` → (interacties) → `browser_unlock`.  
Ook: live HTML-canvases voor demo’s/visualisaties, performance profiling (CPU), en omgaan met dialogen (alert/confirm/prompt).

**Auth:** Geen auth nodig (lokaal browser-MCP).
