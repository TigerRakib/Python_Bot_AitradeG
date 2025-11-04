from pydantic import BaseModel

class BotCreate(BaseModel):
    user_id: str
    api_key: str
    secret_key: str
