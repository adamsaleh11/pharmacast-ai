from pydantic import BaseModel, ConfigDict


class AllowExtraModel(BaseModel):
    model_config = ConfigDict(extra="allow")
