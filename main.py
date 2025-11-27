from fastapi import FastAPI
from api.routes import router



app = FastAPI(
    title="Dashboard Backend API",
    description="Dashboard backend that orchestrates connector negotiation and transfer via connectors",
    version="1.0.0",
)


app.include_router(router=router, prefix="/api")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Dashboard Orchestrator"
    }