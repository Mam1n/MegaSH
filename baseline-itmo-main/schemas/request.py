from typing import List
from pydantic import BaseModel, HttpUrl

class PredictionRequest(BaseModel):
    id: int
    question: str

class PredictionResponse(BaseModel):
    id: int
    answer: str
    reasoning: str
    sources: List[str]  # Изменили на список строк
