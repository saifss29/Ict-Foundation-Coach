from app import app
from extensions import db
from models.quiz_question import QuizQuestion
from models.topic import Topic


QUESTIONS = [
    {
        "topic_slug": "variables",
        "question_text": "Python-e variable-er vitore value assign korte kon sign use hoy?",
        "option_a": "=",
        "option_b": "==",
        "option_c": "+",
        "option_d": "#",
        "correct_option": "A",
        "explanation": "`=` holo assignment operator. Eta variable-er vitore value rakhe.",
        "display_order": 1,
    },
    {
        "topic_slug": "variables",
        "question_text": "`age = 17` line-e `age` ki?",
        "option_a": "Variable",
        "option_b": "Loop",
        "option_c": "Function",
        "option_d": "Comment",
        "correct_option": "A",
        "explanation": "`age` holo variable; ekhane 17 value-ta store kora hoise.",
        "display_order": 2,
    },
    {
        "topic_slug": "if-else",
        "question_text": "`if` condition True hole ki hoy?",
        "option_a": "`if` block-er code run hoy",
        "option_b": "`else` block-er code run hoy",
        "option_c": "Program always stop hoy",
        "option_d": "Kono code run hoy na",
        "correct_option": "A",
        "explanation": "Condition True hole `if` block run hoy.",
        "display_order": 1,
    },
    {
        "topic_slug": "if-else",
        "question_text": "Duita value equal kina compare korte kon operator use hoy?",
        "option_a": "=",
        "option_b": "==",
        "option_c": "!=",
        "option_d": "//",
        "correct_option": "B",
        "explanation": "`==` comparison kore. `=` value assign kore.",
        "display_order": 2,
    },
    {
        "topic_slug": "loops",
        "question_text": "Nirdishto koyekbar same code repeat korte kon loop useful?",
        "option_a": "`if`",
        "option_b": "`for`",
        "option_c": "`else`",
        "option_d": "`print`",
        "correct_option": "B",
        "explanation": "Known number of repetition-er jonno `for` loop useful.",
        "display_order": 1,
    },
    {
        "topic_slug": "loops",
        "question_text": "`while` loop kokhon cholte thake?",
        "option_a": "Condition True thakle",
        "option_b": "Condition False thakle",
        "option_c": "Only ekbar",
        "option_d": "Never",
        "correct_option": "A",
        "explanation": "`while` loop condition True thaka porjonto repeat kore.",
        "display_order": 2,
    },
    {
        "topic_slug": "number-systems",
        "question_text": "Binary number system-er base koto?",
        "option_a": "10",
        "option_b": "8",
        "option_c": "2",
        "option_d": "16",
        "correct_option": "C",
        "explanation": (
            "Binary-er base 2. Ekhane sudhu 0 ar 1 digit use hoy."
        ),
        "display_order": 1,
    },
    {
        "topic_slug": "number-systems",
        "question_text": "Decimal 25-er binary representation konta?",
        "option_a": "11001",
        "option_b": "10101",
        "option_c": "11100",
        "option_d": "10011",
        "correct_option": "A",
        "explanation": (
            "25 = 16 + 8 + 1. Tai 16, 8, 4, 2, 1 position-e "
            "bit hoy 1, 1, 0, 0, 1. Binary result 11001."
        ),
        "display_order": 2,
    },
    {
        "topic_slug": "number-systems",
        "question_text": "Binary 1011-er decimal value koto?",
        "option_a": "9",
        "option_b": "10",
        "option_c": "13",
        "option_d": "11",
        "correct_option": "D",
        "explanation": (
            "1011-er value = 1×8 + 0×4 + 1×2 + 1×1 "
            "= 8 + 2 + 1 = 11."
        ),
        "display_order": 3,
    },
    {
        "topic_slug": "number-systems",
        "question_text": "4-bit binary 1010-er 1's complement konta?",
        "option_a": "1011",
        "option_b": "0101",
        "option_c": "0110",
        "option_d": "1100",
        "correct_option": "B",
        "explanation": (
            "1's complement-e prottek 0 ke 1 ar 1 ke 0 kora hoy. "
            "Tai 1010 → 0101. Ekhane +1 add korte hoy na."
        ),
        "display_order": 4,
    },
    {
        "topic_slug": "number-systems",
        "question_text": "Hexadecimal number system-e A digit-er decimal value koto?",
        "option_a": "8",
        "option_b": "16",
        "option_c": "10",
        "option_d": "11",
        "correct_option": "C",
        "explanation": (
            "Hexadecimal-e 0–9-er por A–F use hoy. "
            "A = 10, B = 11, C = 12, D = 13, E = 14, F = 15."
        ),
        "display_order": 5,
    },
]


with app.app_context():
    topics_by_slug = {
        topic.slug: topic
        for topic in db.session.scalars(db.select(Topic)).all()
    }

    created_count = 0

    for question_data in QUESTIONS:
        topic = topics_by_slug.get(question_data["topic_slug"])

        if topic is None:
            raise RuntimeError(
                f"Topic not found: {question_data['topic_slug']}"
            )

        existing_question = db.session.scalar(
            db.select(QuizQuestion).where(
                QuizQuestion.topic_id == topic.id,
                QuizQuestion.display_order == question_data["display_order"],
            )
        )

        if existing_question is not None:
            continue

        db.session.add(
            QuizQuestion(
                topic_id=topic.id,
                question_text=question_data["question_text"],
                option_a=question_data["option_a"],
                option_b=question_data["option_b"],
                option_c=question_data["option_c"],
                option_d=question_data["option_d"],
                correct_option=question_data["correct_option"],
                explanation=question_data["explanation"],
                display_order=question_data["display_order"],
            )
        )

        created_count += 1

    db.session.commit()

    print(f"{created_count} quiz question(s) created.")