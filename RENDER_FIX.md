# Render Deployment Fix

## 🔧 Update Start Command in Render

Het probleem is dat Python de `models` module niet kan vinden.

### Oplossing: Update Start Command

**Ga naar Render Dashboard → wonderz-agentics → Settings → Start Command**

Verander van:
```
uvicorn api_main:app --host 0.0.0.0 --port 10000
```

Naar:
```
gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT web_ui.backend.api_main:app
```

### OF: Voeg Environment Variable toe

**Environment → Add:**
```
PYTHONPATH=/opt/render/project/src
```

Dan klik op **"Save Changes"** → **"Manual Deploy"** → **"Deploy latest commit"**

---

## ✅ Na Fix

De deployment zou nu moeten slagen. Check de logs voor:
```
Application startup complete
Uvicorn running on http://0.0.0.0:10000
```

Test dan: `curl https://wonderz-agentics.onrender.com/api/crew`
