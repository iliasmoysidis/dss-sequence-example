from fastapi import APIRouter
from services.edcpy_service import run_edcpy_negotiation_and_transfer

router = APIRouter()

@router.post("/connector/initiate")
async def initiate_negotiation_and_transfer(asset_id: str, provider_connector_protocol_url: str, provider_connector_id: str, provider_host: str):
    return await run_edcpy_negotiation_and_transfer(asset_id, provider_connector_protocol_url, provider_connector_id, provider_host)
