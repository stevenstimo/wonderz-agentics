from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/recruit")
async def options_recruit():
    return JSONResponse(status_code=200)

@app.post("/recruit")
async def recruit(request: Request):
    data = await request.json()
    print("RECRUIT DATA:", data)
    return {"ok": True, "received": data}

@app.get("/")
async def root():
    return {"status": "ok"}
