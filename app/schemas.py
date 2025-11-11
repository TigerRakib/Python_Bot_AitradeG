from pydantic import BaseModel,Field
from typing import Literal
class BotCreate(BaseModel):
    user_id: str
    bot_name: str
    api_key: str
    secret_key: str
    duration_days: Literal[2, 7] = Field(..., description="Bot duration in days: 2 or 7")