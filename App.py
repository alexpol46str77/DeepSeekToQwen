import json
import os
import streamlit as st
from openai import OpenAI
from pathlib import Path
import sys
from datetime import datetime
import uuid

# ================= НАСТРОЙКИ =================
BASE_URL = "http://127.0.0.1:1234/v1"
API_KEY = "lm-studio"
MODEL_NAME = "qwen3-vl-8b-instruct"

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

CHATS_DIR = BASE_DIR / "my_chats"
CHATS_DIR.mkdir(exist_ok=True) # Создаем папку, если её нет
# =============================================

def load_all_chats():
    """Читает все JSON файлы из папки my_chats"""
    chats = {}
    for filepath in CHATS_DIR.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                conv = json.load(f)
                
            chat_id = conv.get("id", filepath.stem)
            
            # Если это чат из DeepSeek (со старым форматом mapping)
            if "mapping" in conv:
                mapping = conv["mapping"]
                title = conv.get("title") or "Диалог DeepSeek"
                date_str = conv.get("inserted_at", "")
                
                messages = []
                # (здесь ваш старый код парсинга mapping, я его сократил для читаемости, 
                #  но он должен быть точно таким же, как в прошлом app.py)
                nodes = list(mapping.values())
                nodes.sort(key=lambda n: (n.get("message") or {}).get("inserted_at", ""))
                for node in nodes:
                    msg = node.get("message")
                    if not msg: continue
                    role = msg.get("role") or (msg.get("author", {}).get("role") if isinstance(msg.get("author"), dict) else None)
                    text_parts = []
                    for frag in msg.get("fragments", []):
                        if frag.get("type", "").upper() in ("REQUEST", "RESPONSE"):
                            c = frag.get("content") or frag.get("text")
                            if c: text_parts.append(c)
                    if not text_parts and msg.get("content"): text_parts.append(msg["content"])
                    text = "\n".join(text_parts).strip()
                    if text: messages.append({"role": role, "content": text})
                    
            # Если это наш новый локальный чат
            else:
                title = conv.get("title", "Новый чат")
                date_str = conv.get("date", datetime.now().isoformat())
                messages = conv.get("messages", [])

            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except:
                dt = datetime.min

            chats[chat_id] = {
                "title": title,
                "messages": messages,
                "date": dt,
                "date_str": date_str,
                "filepath": filepath # Запоминаем путь для сохранения
            }
        except Exception as e:
            print(f"Ошибка чтения {filepath}: {e}")
            
    return chats

def save_chat(chat_id, title, messages, filepath):
    """Сохраняет текущий чат в файл"""
    data = {
        "id": chat_id,
        "title": title,
        "date": datetime.now().isoformat(),
        "messages": messages
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def trim_history(history, max_msgs):
    if len(history) <= max_msgs: return history
    trimmed = history[-max_msgs:]
    while trimmed and trimmed[0]["role"] != "user": trimmed = trimmed[1:]
    return trimmed

# ================== ИНТЕРФЕЙС ==================
st.set_page_config(page_title="DeepSeek → Qwen", page_icon="💬", layout="wide")
st.title("💬 Мои чаты с Qwen")

# Загружаем чаты
if "all_chats" not in st.session_state:
    st.session_state.all_chats = load_all_chats()

all_chats = st.session_state.all_chats

# --- Сайдбар ---
with st.sidebar:
    st.header("⚙️ Управление")
    
    if st.button("🔄 Обновить список файлов", use_container_width=True):
        st.session_state.all_chats = load_all_chats()
        st.rerun()

    if st.button("➕ Создать новый чат", use_container_width=True):
        new_id = str(uuid.uuid4())
        filename = CHATS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}_Новый_{new_id[:8]}.json"
        save_chat(new_id, "Новый чат", [], filename)
        st.session_state.all_chats = load_all_chats()
        st.session_state.current_chat_id = new_id # Переключаемся на него
        st.rerun()

    st.divider()

    # Сортировка по дате
    sorted_chat_ids = sorted(all_chats.keys(), key=lambda k: all_chats[k]["date"], reverse=True)
    chat_options = {}
    for cid in sorted_chat_ids:
        chat = all_chats[cid]
        date_disp = chat["date"].strftime("%Y-%m-%d") if chat["date"] != datetime.min else "Без даты"
        chat_options[cid] = f"[{date_disp}] {chat['title']} ({len(chat['messages'])} с.)"
    
    # Если текущий чат не выбран, выбираем первый
    if "current_chat_id" not in st.session_state or st.session_state.current_chat_id not in all_chats:
        st.session_state.current_chat_id = sorted_chat_ids[0] if sorted_chat_ids else None

    selected_chat_id = st.selectbox(
        "Выберите чат",
        options=sorted_chat_ids,
        index=sorted_chat_ids.index(st.session_state.current_chat_id) if st.session_state.current_chat_id in sorted_chat_ids else 0,
        format_func=lambda x: chat_options[x]
    )
    
    # Если пользователь переключил чат в селектбоксе
    if selected_chat_id != st.session_state.current_chat_id:
        st.session_state.current_chat_id = selected_chat_id
        st.rerun()

    st.divider()
    max_msgs = st.slider("Сообщений в контексте", 5, 100, 30, step=5)
    temperature = st.slider("Температура", 0.0, 1.5, 0.7, step=0.1)
    max_tokens = st.slider("Макс. токенов", 128, 4096, 1024, step=128)

# --- Отображение и логика текущего чата ---
if not st.session_state.current_chat_id:
    st.info("Нет ни одного чата. Нажмите 'Создать новый чат' в меню слева.")
    st.stop()

current_chat = all_chats[st.session_state.current_chat_id]

# --- Отображение чата ---
show_last = max(max_msgs, 50)
for msg in current_chat["messages"][-show_last:]:
        role_name = str(msg.get("role", "user"))
        with st.chat_message(name=role_name):
            st.markdown(msg["content"])
# --- Ввод ---
# --- Ввод ---
user_input = st.chat_input("Напишите сообщение...")
if user_input:
    # 1. Добавляем сообщение пользователя в текущий чат
    current_chat["messages"].append({"role": "user", "content": user_input})
    
    # 2. Отображаем его в интерфейсе
    with st.chat_message(name="user"):
        st.markdown(user_input)

    # 3. Готовим контекст (обрезаем)
    context = trim_history(current_chat["messages"], max_msgs)
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    # 4. Идем к Qwen
    with st.chat_message(name="assistant"):
        with st.spinner("Qwen думает..."):
            try:
                completion = client.chat.completions.create(
                    model=MODEL_NAME, messages=context,
                    max_tokens=max_tokens, temperature=temperature,
                )
                reply = completion.choices[0].message.content
            except Exception as e:
                reply = f"⚠️ Ошибка: {e}"
        st.markdown(reply)

    # 5. Добавляем ответ и СОХРАНЯЕМ НА ДИСК
    current_chat["messages"].append({"role": "assistant", "content": reply})
    
    # Берем путь к файлу из загруженных данных и сохраняем
    save_chat(
        chat_id=st.session_state.current_chat_id,
        title=current_chat["title"],
        messages=current_chat["messages"],
        filepath=current_chat["filepath"]
    )
    
    # 6. Перезапускаем интерфейс, чтобы он подхватил новый список чатов (сортировка по дате обновится)
    st.rerun()