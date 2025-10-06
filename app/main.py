from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import cloth, design, user, auth

app = FastAPI(
    title="LSP Apperal API",
    description="API for managing garment factory operations.",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Include all the routers
app.include_router(cloth.router)
app.include_router(design.router)
app.include_router(user.router)
app.include_router(auth.router)

# REMOVE or COMMENT OUT the old root endpoint
# @app.get("/", include_in_schema=False)
# def read_root():
#     return {"message": "Welcome to LSP Apperal API"}

@app.get("/health", tags=["Health Check"])
def health_check():
    """
    Check if the API is running.
    """
    return {"status": "ok"}