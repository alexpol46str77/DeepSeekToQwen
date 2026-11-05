import json
import os
from openai import OpenAI

# ================= НАСТРОЙКИ ДЛЯ LM STUDIO =================
BASE_URL = "http://127.0.0.1:1234/v1"
API_KEY = "lm-studio"
# Точное имя модели
MODEL_NAME = "qwen3-vl-8b-instruct" 

DEEPSEEK_JSON_PATH = "conversations.json" 
# ============================================================


def load_deepseek_history(file_path):
    """Загружает и разбирает conversations.json, экспортированный из DeepSeek."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    history = []

    # data — это список чатов
    for conv in data:
        mapping = conv.get("mapping", {})
        if not mapping:
            continue

        # Собираем все узлы в список
        nodes = list(mapping.values())

        # Сортируем узлы по времени создания (inserted_at), если оно есть
        # Это даёт правильный порядок сообщений
        def get_time(node):
            msg = node.get("message") or {}
            return msg.get("inserted_at") or node.get("inserted_at") or ""

        nodes.sort(key=get_time)

        for node in nodes:
            message = node.get("message")
            if not message:
                continue

            # Определяем роль
            role = None
            # DeepSeek может использовать поле "role" или определять по "model"
            if "role" in message:
                role = message["role"]
            elif "author" in message and isinstance(message["author"], dict):
                role = message["author"].get("role")
            # Если роль не указана, но есть fragments с типом REQUEST — это пользователь
            # а если RESPONSE — это ассистент
            fragments = message.get("fragments", [])
            if not role:
                for frag in fragments:
                    frag_type = frag.get("type", "").upper()
                    if frag_type == "REQUEST":
                        role = "user"
                        break
                    elif frag_type == "RESPONSE":
                        role = "assistant"
                        break

            if role not in ("user", "assistant"):
                continue

            # Извлекаем текст из fragments
            text_parts = []
            for frag in fragments:
                frag_type = frag.get("type", "").upper()
                # Берём только REQUEST (вопрос пользователя) и RESPONSE (ответ ассистента)
                # Игнорируем SEARCH и другие служебные типы
                if frag_type in ("REQUEST", "RESPONSE"):
                    # У фрагмента может быть поле "content"
                    content = frag.get("content")
                    if content:
                        text_parts.append(content)
                    # Иногда текст лежит в "text"
                    elif frag.get("text"):
                        text_parts.append(frag["text"])

            # Если в fragments ничего не нашли, но есть обычное поле "content"
            if not text_parts and message.get("content"):
                text_parts.append(message["content"])

            text = "\n".join(text_parts).strip()
            if not text:
                continue

            history.append({
                "role": role,
                "content": text
            })

    if not history:
        print("⚠️ Не удалось найти сообщения в conversations.json.")
        print("Вот первые 1000 символов файла для отладки:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
    else:
        print(f"✅ Успешно загружено сообщений: {len(history)}")

    return history

def chat_with_history(history):
    """Отправляет историю как контекст в LM Studio и ведёт диалог."""
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    # Ограничиваем историю последними 20 сообщениями, чтобы не переполнить контекст
    # Qwen3-VL-8B имеет лимит, и слишком длинная история может его превысить.
    MAX_HISTORY_MSGS = 20
    if len(history) > MAX_HISTORY_MSGS:
        print(f"⚠️ История слишком длинная ({len(history)} сообщений). Оставляю последние {MAX_HISTORY_MSGS}.")
        history = history[-MAX_HISTORY_MSGS:]

    messages = history.copy()
    
    # Системная инструкция (можно убрать, если мешает)
    system_prompt = {
        "role": "system",
        "content": "Ты — ассистент, который помнит нашу прошлую переписку. Опирайся на неё, отвечая на новые вопросы."
    }
    messages.insert(0, system_prompt)

    print("\n=== Контекст загружен. Диалог начат. Введите 'exit' для выхода ===")

    while True:
        user_input = input("\nВы: ")
        if user_input.lower() in ("exit", "quit", "q"):
            print("Выход.")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                max_tokens=1024,
                temperature=0.7
            )

            assistant_reply = completion.choices[0].message.content
            print(f"\nQwen: {assistant_reply}")

            messages.append({"role": "assistant", "content": assistant_reply})

        except Exception as e:
            print(f"\n[Ошибка] Не удалось получить ответ: {e}")
            messages.pop()


if __name__ == "__main__":
    try:
        deepseek_history = load_deepseek_history(DEEPSEEK_JSON_PATH)
        chat_with_history(deepseek_history)
    except Exception as e:
        print(f"Ошибка инициализации: {e}")