from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import cloth, design, user, auth, production

app = FastAPI(
    title="LSP Apperal API",
    description="API for managing garment factory operations.",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(cloth.router)
app.include_router(design.router)
app.include_router(user.router)
app.include_router(auth.router)
app.include_router(production.router)

@app.get("/health", tags=["Health Check"])
def health_check():
    return {"status": "ok"}