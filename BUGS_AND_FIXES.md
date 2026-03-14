# Bugs and fixes

## Bug #13

- **Bestand:** app/events.py regel 73
- **Fout:** `dict(r["payload"])` crasht wanneer payload een dubbel-encoded JSON string is
- **Fix:** `_coerce_payload()` unwrap helper toegevoegd die de string eerst parsed voor dict-conversie
- **Commit:** f0218d2
- **Datum:** 14 maart 2026
