import random
import streamlit as st
from database import (
    init_db, get_or_create_user, get_user_words, add_word,
    remove_user_word, get_random_question, save_answer, get_statistics
)

st.set_page_config(page_title="EnglishCard", page_icon="📚", layout="wide")

@st.cache_resource
def prepare_database():
    init_db()

prepare_database()

st.title("📚 EnglishCard")
st.write("Привет 👋 Давай попрактикуемся в английском языке!")
st.write(
    "Тренировки можно проходить в удобном темпе. "
    "Добавляй собственные слова и собирай личный словарь."
)

with st.sidebar:
    st.header("Пользователь")
    username = st.text_input(
        "Введите имя пользователя",
        value=st.session_state.get("username", ""),
        placeholder="Например, alex"
    ).strip()

    if st.button("Войти / создать профиль", use_container_width=True):
        if not username:
            st.error("Введите имя пользователя.")
        else:
            user_id = get_or_create_user(username)
            st.session_state["user_id"] = user_id
            st.session_state["username"] = username
            st.session_state.pop("question", None)
            st.success(f"Профиль «{username}» готов!")

    if st.session_state.get("user_id"):
        st.success(f"Вы вошли как: {st.session_state['username']}")
        if st.button("Выйти", use_container_width=True):
            for key in ("user_id", "username", "question", "feedback"):
                st.session_state.pop(key, None)
            st.rerun()

if not st.session_state.get("user_id"):
    st.info("Чтобы начать, введите имя пользователя в боковой панели и нажмите «Войти / создать профиль».")
    st.stop()

user_id = st.session_state["user_id"]
tab_train, tab_words, tab_stats = st.tabs(["🎯 Тренировка", "📖 Мои слова", "📊 Статистика"])

with tab_train:
    st.subheader("Выбери правильный перевод")

    if st.session_state.get("question") is None and not st.session_state.get("feedback"):
        st.session_state["question"] = get_random_question(user_id)

    if st.session_state.get("feedback"):
        kind, message = st.session_state["feedback"]
        getattr(st, kind)(message)
        if kind == "error":
            if st.button("Попробовать ещё раз", type="primary"):
                st.session_state.pop("feedback", None)
                st.rerun()
        else:
            if st.button("Следующее слово", type="primary"):
                st.session_state.pop("feedback", None)
                st.session_state["question"] = get_random_question(user_id)
                st.rerun()
    else:
        question = st.session_state.get("question")
        if question is None:
            st.warning("В словаре пока недостаточно слов для тренировки.")
        else:
            st.markdown(f"### {question['russian_word']}")
            st.caption("Как это слово переводится на английский?")
            cols = st.columns(2)
            for index, option in enumerate(question["options"]):
                with cols[index % 2]:
                    if st.button(option, key=f"answer_{question['word_id']}_{index}", use_container_width=True):
                        correct = option == question["english_word"]
                        save_answer(user_id, question["word_id"], correct)
                        st.session_state["feedback"] = (
                            ("success", f"Верно! «{question['russian_word']}» — {question['english_word']}.")
                            if correct else
                            ("error", "Не совсем верно. Правильный перевод: "
                             f"{question['english_word']}. Попробуй следующее слово!")
                        )
                        st.rerun()

with tab_words:
    st.subheader("Мой словарь")
    with st.expander("➕ Добавить новое слово", expanded=False):
        with st.form("add_word_form", clear_on_submit=True):
            russian = st.text_input("Слово на русском")
            english = st.text_input("Перевод на английском")
            submitted = st.form_submit_button("Добавить слово")
            if submitted:
                try:
                    if add_word(user_id, russian, english):
                        st.success("Слово добавлено в ваш личный словарь.")
                        st.rerun()
                    else:
                        st.warning("Это слово уже есть в вашем словаре.")
                except ValueError as exc:
                    st.error(str(exc))

    words = get_user_words(user_id)
    st.write(f"Всего слов: **{len(words)}**")
    if not words:
        st.info("Словарь пуст.")
    else:
        for word in words:
            left, right = st.columns([5, 1])
            left.write(f"**{word['russian_word']}** — {word['english_word']}")
            if right.button("🗑️", key=f"delete_{word['word_id']}", help="Удалить слово из личного словаря"):
                remove_user_word(user_id, word["word_id"])
                st.rerun()

with tab_stats:
    st.subheader("Мои результаты")
    stats = get_statistics(user_id)
    c1, c2, c3 = st.columns(3)
    c1.metric("Всего ответов", stats["total"])
    c2.metric("Правильных ответов", stats["correct"])
    c3.metric("Точность", f"{stats['accuracy']:.1f}%")
    if stats["total"] == 0:
        st.info("Пока нет ответов. Пройдите тренировку, чтобы появилась статистика.")
    else:
        st.progress(stats["correct"] / stats["total"])
