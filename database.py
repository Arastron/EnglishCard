import os
import random
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    """Создаёт подключение к PostgreSQL из переменных окружения."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "englishcard"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


@contextmanager
def get_cursor():
    connection = get_connection()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
    finally:
        connection.close()


def init_db():
    """Создаёт таблицы и заполняет общий словарь."""
    with get_cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS words (
                word_id SERIAL PRIMARY KEY,
                russian_word VARCHAR(100) NOT NULL,
                english_word VARCHAR(100) NOT NULL,
                owner_user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (owner_user_id, russian_word, english_word)
            );

            CREATE TABLE IF NOT EXISTS user_words (
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                word_id INTEGER NOT NULL REFERENCES words(word_id) ON DELETE CASCADE,
                added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, word_id)
            );

            CREATE TABLE IF NOT EXISTS user_answers (
                answer_id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                word_id INTEGER NOT NULL REFERENCES words(word_id) ON DELETE CASCADE,
                is_correct BOOLEAN NOT NULL,
                answered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)

        common_words = [
            ("красный", "red"),
            ("синий", "blue"),
            ("зелёный", "green"),
            ("жёлтый", "yellow"),
            ("чёрный", "black"),
            ("белый", "white"),
            ("я", "I"),
            ("ты", "you"),
            ("он", "he"),
            ("она", "she"),
        ]
        for russian, english in common_words:
            cursor.execute("""
                INSERT INTO words (russian_word, english_word, owner_user_id)
                SELECT %s, %s, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM words
                    WHERE owner_user_id IS NULL
                      AND LOWER(russian_word) = LOWER(%s)
                      AND LOWER(english_word) = LOWER(%s)
                )
            """, (russian, english, russian, english))


def get_or_create_user(username):
    username = username.strip()
    if not username or len(username) > 50:
        raise ValueError("Имя пользователя должно содержать от 1 до 50 символов.")

    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (username)
            VALUES (%s)
            ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
            RETURNING user_id
        """, (username,))
        user_id = cursor.fetchone()["user_id"]

        cursor.execute("""
            INSERT INTO user_words (user_id, word_id)
            SELECT %s, word_id FROM words WHERE owner_user_id IS NULL
            ON CONFLICT DO NOTHING
        """, (user_id,))
        return user_id


def get_user_words(user_id):
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT w.word_id, w.russian_word, w.english_word
            FROM words w
            JOIN user_words uw ON uw.word_id = w.word_id
            WHERE uw.user_id = %s
            ORDER BY w.russian_word
        """, (user_id,))
        return cursor.fetchall()


def add_word(user_id, russian_word, english_word):
    russian_word = russian_word.strip()
    english_word = english_word.strip()
    if not russian_word or not english_word:
        raise ValueError("Заполните оба поля.")
    if len(russian_word) > 100 or len(english_word) > 100:
        raise ValueError("Длина каждого слова не должна превышать 100 символов.")

    with get_cursor() as cursor:
        cursor.execute("""
            SELECT word_id FROM words
            WHERE owner_user_id = %s
              AND LOWER(russian_word) = LOWER(%s)
              AND LOWER(english_word) = LOWER(%s)
        """, (user_id, russian_word, english_word))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                INSERT INTO user_words (user_id, word_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (user_id, existing["word_id"]))
            return False

        cursor.execute("""
            INSERT INTO words (russian_word, english_word, owner_user_id)
            VALUES (%s, %s, %s)
            RETURNING word_id
        """, (russian_word, english_word, user_id))
        word_id = cursor.fetchone()["word_id"]
        cursor.execute("""
            INSERT INTO user_words (user_id, word_id) VALUES (%s, %s)
        """, (user_id, word_id))
        return True


def remove_user_word(user_id, word_id):
    with get_cursor() as cursor:
        cursor.execute("""
            DELETE FROM user_words
            WHERE user_id = %s AND word_id = %s
        """, (user_id, word_id))


def get_random_question(user_id):
    words = get_user_words(user_id)
    if len(words) < 4:
        return None

    correct_word = random.choice(words)
    distractors = [
        word["english_word"] for word in words
        if word["word_id"] != correct_word["word_id"]
    ]
    options = random.sample(distractors, 3) + [correct_word["english_word"]]
    random.shuffle(options)

    return {
        "word_id": correct_word["word_id"],
        "russian_word": correct_word["russian_word"],
        "english_word": correct_word["english_word"],
        "options": options,
    }


def save_answer(user_id, word_id, is_correct):
    with get_cursor() as cursor:
        cursor.execute("""
            INSERT INTO user_answers (user_id, word_id, is_correct)
            VALUES (%s, %s, %s)
        """, (user_id, word_id, is_correct))


def get_statistics(user_id):
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE is_correct) AS correct
            FROM user_answers
            WHERE user_id = %s
        """, (user_id,))
        row = cursor.fetchone()
        total = row["total"] or 0
        correct = row["correct"] or 0
        accuracy = (correct / total * 100) if total else 0
        return {"total": total, "correct": correct, "accuracy": accuracy}
