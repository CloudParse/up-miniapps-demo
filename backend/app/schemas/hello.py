from app.schemas.base import CamelModel


class Greeting(CamelModel):
    message: str
