INSERT INTO words (russian_word, english_word, owner_user_id)
SELECT v.russian_word, v.english_word, NULL
FROM (VALUES
    ('красный', 'red'),
    ('синий', 'blue'),
    ('зелёный', 'green'),
    ('жёлтый', 'yellow'),
    ('чёрный', 'black'),
    ('белый', 'white'),
    ('я', 'I'),
    ('ты', 'you'),
    ('он', 'he'),
    ('она', 'she')
) AS v(russian_word, english_word)
WHERE NOT EXISTS (
    SELECT 1 FROM words w
    WHERE w.owner_user_id IS NULL
      AND LOWER(w.russian_word) = LOWER(v.russian_word)
      AND LOWER(w.english_word) = LOWER(v.english_word)
);
