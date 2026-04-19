from pydantic import BaseModel


class ForecastPlaceholder(BaseModel):
    ready: bool = False

