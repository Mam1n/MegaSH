import time
import openai
import os
import googleapiclient.discovery
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from schemas.request import PredictionRequest, PredictionResponse
from utils.logger import setup_logger
import asyncio

# Инициализация FastAPI
app = FastAPI()
logger = None

# Ваши API ключи для OpenAI (ChatGPT) и API ключ Google
openai.api_key = os.getenv("OPENAI_API_KEY")  # Чтение API ключа из переменной окружения
google_api_key = "AIzaSyAuNEpZoW9lIQ6ZxF44XWDMBH6FD2EgfRc"  # Ваш ключ API для Google
cse_id = "9751498b196d34387"  # Ваш CSE ID

# Функция для получения ответа от ChatGPT
async def get_chatgpt_answer(question: str) -> str:
    try:
        response = await openai.Completion.create(
            model="gpt-4",  # Или другой доступный вариант модели
            prompt=question,
            max_tokens=150
        )
        if response.choices:
            return response.choices[0].text.strip()
        else:
            return "Ответ от ChatGPT не получен."
    except Exception as e:
        logger.error(f"Ошибка в get_chatgpt_answer: {str(e)}")
        return f"Ошибка ChatGPT: {str(e)}"

# Функция для выполнения поиска через Google API
async def search_google(question: str) -> str:
    try:
        # Создаём сервис для работы с поисковым API
        service = googleapiclient.discovery.build("customsearch", "v1", developerKey=google_api_key)

        # Выполняем запрос с использованием асинхронности
        res = await asyncio.to_thread(service.cse().list, q=question, cx=cse_id)

        # Извлекаем результаты из ответа
        results = []
        for item in res.get("items", []):
            title = item.get("title")
            link = item.get("link")
            snippet = item.get("snippet")
            results.append(f"{title}: {snippet}\n{link}")

        return "\n".join(results[:3]) if results else "Не найдено результатов."
    
    except Exception as e:
        return f"Ошибка при запросе к Google API: {str(e)}"

# Функция для комбинированного ответа с использованием поиска по Google и ChatGPT
async def get_combined_answer(question: str) -> str:
    try:
        # Получаем ответ от ChatGPT
        chatgpt_answer = await get_chatgpt_answer(question)

        # Получаем информацию через поиск Google
        search_answer = await search_google(question)

        # Объединяем ответы
        combined_answer = f"Ответ ChatGPT: {chatgpt_answer}\n\nРезультаты поиска:\n{search_answer}"
        return combined_answer.strip()
    except Exception as e:
        return f"Произошла ошибка при обработке запроса: {str(e)}"

@app.post("/api/request", response_model=PredictionResponse, summary="Получение ответа на вопрос о ИТМО")
async def predict(body: PredictionRequest):
    """
    Получить ответ на вопрос, комбинируя информацию от ChatGPT и из поисковых результатов Google.
    """
    try:
        await logger.info(f"Обрабатывается запрос с id: {body.id}")
        combined_answer = await get_combined_answer(body.question)
        response = PredictionResponse(
            id=body.id,
            answer=combined_answer,
            reasoning="Ответ на основе ChatGPT и информации из поисковых результатов Google.",
            sources=["https://itmo.ru/ru/"]  # Источник
        )

        await logger.info(f"Успешно обработан запрос {body.id}")
        return response
    except Exception as e:
        await logger.error(f"Ошибка при обработке запроса {body.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@app.on_event("startup")
async def startup_event():
    global logger
    logger = await setup_logger()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    body = await request.body()
    await logger.info(
        f"Получен запрос: {request.method} {request.url}\n"
        f"Тело запроса: {body.decode()}"
    )
    response = await call_next(request)
    process_time = time.time() - start_time
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk
    await logger.info(
        f"Запрос завершен: {request.method} {request.url}\n"
        f"Статус: {response.status_code}\n"
        f"Тело ответа: {response_body.decode()}\n"
        f"Время обработки: {process_time:.3f}s"
    )
    return Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )
