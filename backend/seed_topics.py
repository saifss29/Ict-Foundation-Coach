from app import app
from extensions import db
from models.topic import Topic
from services.topic_cache_service import invalidate_topic_cache


TOPICS = [
    {
        "title": "SSC ICT",
        "slug": "ssc-ict",
        "description": (
            "ICT niye question koro, tutor-er sathe bujhe nao, "
            "ar discussion-er upor quiz diye practice koro."
        ),
        "display_order": 0,
        "subject": "ict",
        "academic_level": "ssc",
    },
    {
        "title": "HSC ICT",
        "slug": "hsc-ict",
        "description": (
            "ICT niye question koro, tutor-er sathe bujhe nao, "
            "ar discussion-er upor quiz diye practice koro."
        ),
        "display_order": 0,
        "subject": "ict",
        "academic_level": "hsc",
    },
    {
        "title": "Variables",
        "slug": "variables",
        "description": "Python-e named container diye data store and reuse kora.",
        "display_order": 1,
        "subject": "ict",
        "academic_level": "hsc",
    },
    {
        "title": "If-Else",
        "slug": "if-else",
        "description": "Condition true na false hole program ki decision nibe.",
        "display_order": 2,
        "subject": "ict",
        "academic_level": "hsc",
    },
    {
        "title": "Loops",
        "slug": "loops",
        "description": "Same instruction controlled way-te repeat kora.",
        "display_order": 3,
        "subject": "ict",
        "academic_level": "hsc",
    },
    {
        "title": "Number Systems",
        "slug": "number-systems",
        "description": (
            "Binary, decimal, octal, hexadecimal ar "
            "number conversion-er fundamentals."
        ),
        "display_order": 4,
        "subject": "ict",
        "academic_level": "hsc",
    },
]

SSC_ICT_LESSONS = [
    ("ict-in-everyday-life", "ICT in everyday life"),
    ("e-learning", "E-learning"),
    ("e-governance-and-e-services", "E-governance and e-services"),
    ("e-commerce", "E-commerce"),
    (
        "preventive-and-corrective-maintenance",
        "Preventive and corrective maintenance",
    ),
    (
        "installing-and-uninstalling-software",
        "Installing and uninstalling software",
    ),
    (
        "public-and-confidential-information",
        "Public and confidential information",
    ),
    (
        "cyber-risks-and-responsible-access",
        "Cyber risks and responsible access",
    ),
    ("internet-and-digital-content", "Internet and digital content"),
    ("e-books-and-learning-resources", "E-books and learning resources"),
    ("word-processing", "Word processing"),
    ("save-and-save-as", "Save and Save As"),
    (
        "document-formatting-and-tables",
        "Document formatting and tables",
    ),
    (
        "spreadsheets-and-cell-references",
        "Spreadsheets and cell references",
    ),
    ("multimedia-and-interactivity", "Multimedia and interactivity"),
    ("planning-a-presentation", "Planning a presentation"),
    ("problem-solving-before-coding", "Problem solving before coding"),
    ("python-output-and-variables", "Python output and variables"),
    ("python-input-and-arithmetic", "Python input and arithmetic"),
    ("python-decisions", "Python decisions"),
    ("python-repetition-and-range", "Python repetition and range"),
    ("bits-and-bytes-hsc-bridge", "Bits and bytes: HSC bridge"),
    ("binary-place-value-hsc-bridge", "Binary place value: HSC bridge"),
    (
        "first-html-page-optional-practice",
        "First HTML page: optional practice",
    ),
    ("files-before-web-development", "Files before web development"),
]

TOPICS.extend(
    {
        "title": title,
        "slug": f"ssc-ict-{slug}",
        "description": f"{title} niye ICT practice koro.",
        "display_order": index,
        "subject": "ict",
        "academic_level": "ssc",
    }
    for index, (slug, title) in enumerate(
        SSC_ICT_LESSONS,
        start=1,
    )
)


with app.app_context():
    created_count = 0

    for topic_data in TOPICS:
        existing_topic = db.session.scalar(
            db.select(Topic).where(
                Topic.slug == topic_data["slug"]
            )
        )

        if existing_topic is not None:
            continue

        db.session.add(Topic(**topic_data))
        created_count += 1

    db.session.commit()

    if created_count > 0:
        cache_cleared = invalidate_topic_cache()

        if cache_cleared:
            print("Topic cache invalidated.")
        else:
            print(
                "Topic cache was not invalidated. "
                "Existing cached entries expire within 5 minutes."
            )

    print(f"{created_count} topic(s) created.")