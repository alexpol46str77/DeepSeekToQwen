import json
import os
import uuid
from pathlib import Path

# Имя СТАРОГО файла с историей
JSON_PATH = "conversations.json" 
OUT_DIR = Path("my_chats")
OUT_DIR.mkdir(exist_ok=True) # Создаем папку my_chats, если её нет

if not os.path.exists(JSON_PATH):
    print(f"Ошибка: Файл {JSON_PATH} не найден в этой папке!")
else:
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for conv in data:
        # Берем ID чата или генерируем новый
        chat_id = conv.get("id", str(uuid.uuid4()))
        title = conv.get("title", "Без названия").replace("/", "_").replace("\\", "_").replace('"', '')
        
        # Формируем красивое имя файла: дата_название_id.json
        date = conv.get("inserted_at", "")[:10] or "no_date"
        filename = f"{date}_{title[:30]}_{chat_id}.json"
        
        # Сохраняем чат в отдельный файл
        with open(OUT_DIR / filename, "w", encoding="utf-8") as f_out:
            json.dump(conv, f_out, ensure_ascii=False, indent=2)
        count += 1

    print(f"Успех! Разбито на {count} отдельных чатов в папке my_chats.")