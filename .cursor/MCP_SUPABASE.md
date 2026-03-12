# Supabase MCP — token-auth (geen OAuth/client_id)

Om de fout "Unrecognized client_id" te omzeilen gebruik je een **Personal Access Token (PAT)** in plaats van OAuth.

## Stappen

1. **PAT aanmaken**
   - Ga naar [Supabase Access Tokens](https://supabase.com/dashboard/account/tokens).
   - Maak een nieuw token (bijv. "Cursor MCP").
   - Kopieer het token (eenmalig zichtbaar).

2. **Token in MCP-config zetten**
   - Open `.cursor/mcp.json` (als die nog niet bestaat: kopieer `.cursor/mcp.json.example` naar `.cursor/mcp.json`).
   - Vervang `YOUR_SUPABASE_PAT_HERE` door je echte token.
   - Bewaar het bestand (het staat in `.gitignore`, dus wordt niet gecommit).

3. **Cursor herstarten**
   - Sluit Cursor volledig en start opnieuw.
   - De Supabase MCP-server gebruikt nu token-auth; je hoeft geen `mcp_auth` meer te doen.

## Project

De config is gekoppeld aan project `cqasccazioqjodctawzx` via `project_ref` in de URL. Voor een ander project pas je `project_ref` in `.cursor/mcp.json` aan.