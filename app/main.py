from fastapi import FastAPI
from app.routers import cloth, design, user

app = FastAPI(
    title="LSP Apperal API",
    description="API for managing garment factory operations.",
    version="1.0.0"
)

# Include the routers
app.include_router(cloth.router)
app.include_router(design.router)
app.include_router(user.router)


@app.get("/", include_in_schema=False)
def read_root():
    return {"message": "Welcome to LSP Apperal API"}

@app.get("/health", tags=["Health Check"])
def health_check():
    """
    Check if the API is running.
    """
    return {"status": "ok"}