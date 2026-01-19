import os
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI  # Асинхронный клиент
import httpx  # Асинхронные HTTP запросы

app = FastAPI()

# Инициализируем асинхронный клиент OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")

if not os.getenv("OPENAI_API_KEY") or not CURRENTS_API_KEY:
    raise ValueError("Переменные окружения OPENAI_API_KEY и CURRENTS_API_KEY должны быть установлены")

class Topic(BaseModel):
    topic: str

# Асинхронная функция получения новостей
async def get_recent_news(topic: str):
    url = "https://api.currentsapi.services/v1/latest-news"
    params = {
        "language": "en",
        "keywords": topic,
        "apiKey": CURRENTS_API_KEY
    }
    
    # Используем асинхронный контекстный менеджер для httpx
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            news_data = response.json().get("news", [])
            
            if not news_data:
                return "Свежих новостей не найдено."
            
            return "\n".join([article["title"] for article in news_data[:5]])
        except Exception as e:
            print(f"Ошибка Currents API: {e}")
            return "Актуальные новости недоступны на данный момент."

# Асинхронная генерация контента
async def generate_content(topic: str):
    # Дожидаемся получения новостей
    recent_news = await get_recent_news(topic)

    try:
        # Запускаем генерацию заголовка
        title_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user", 
                "content": f"Придумайте заголовок для статьи на тему '{topic}', учитывая новости:\n{recent_news}"
            }],
            max_tokens=60,
            temperature=0.5
        )
        title = title_response.choices[0].message.content.strip()

        # Генерация мета-описания
        meta_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user", 
                "content": f"Напишите SEO мета-описание для статьи: '{title}'"
            }],
            max_tokens=150,
            temperature=0.5
        )
        meta_description = meta_response.choices[0].message.content.strip()

        # Генерация основного текста
        post_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user", 
                "content": f"Напишите подробную статью на тему '{topic}', опираясь на новости:\n{recent_news}. Используйте подзаголовки."
            }],
            max_tokens=1500,
            temperature=0.7
        )
        post_content = post_response.choices[0].message.content.strip()

        return {
            "title": title,
            "meta_description": meta_description,
            "post_content": post_content
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {str(e)}")

@app.post("/generate-post")
async def generate_post_api(topic: Topic):
    # Вызываем асинхронную функцию через await
    return await generate_content(topic.topic)

@app.get("/health")
async def health():
    return {"status": "OK", "mode": "asynchronous"}

if __name__ == "__main__":
    import uvicorn
    # Запуск
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
