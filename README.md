# ICT Foundation Coach

ICT Foundation Coach is a learning platform designed to help Bangladeshi SSC and HSC students strengthen their ICT fundamentals through a Banglish AI tutor, quizzes, assignments, and progress tracking.

Developed as an individual internship project for **GigaLogy Ltd**.

## Features

### Students

- Register, verify email, log in, and reset passwords.
- Learn through an AI tutor powered by GigaLogy Maira.
- Revisit previous conversations through chat history.
- Practice topic-based and AI-generated quizzes.
- Join classrooms and complete assigned quizzes, learning assignments, and class exams.
- View results, teacher feedback, and learning progress.
- Communicate through direct messages.
- Manage calendar events and receive notifications.

### Teachers

- Create and manage classrooms.
- Generate, review, and assign quizzes.
- Create learning assignments and class exams.
- Review student submissions and provide feedback.
- Monitor student performance and classroom progress.
- Communicate with students through direct messages.

### Additional Features

- Parent email verification and weekly progress reports.
- Calendar reminders and AI-assisted calendar functionality.
- Redis-backed topic caching and API rate limiting.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Vue 3, Composition API, Vue Router, Vuex, Vite, CSS |
| Backend | Flask, SQLAlchemy, Marshmallow |
| Authentication | Flask-JWT-Extended |
| Database | PostgreSQL |
| Migrations | Flask-Migrate, Alembic |
| Caching and rate limiting | Redis, Flask-Limiter |
| AI integration | GigaLogy Maira |
| Email | SMTP |
| Testing | pytest |
| Runtime | Docker Compose, Gunicorn, Nginx |

## Project Structure

```text
backend/
  app.py
  config.py
  models/
  routes/
  schemas/
  services/
  migrations/
  datasets/
  tests/
  seed_topics.py
  seed_quiz_questions.py
  weekly_report_worker.py
  requirements.txt
  Dockerfile

frontend/
  src/
    components/
    views/
    router/
    store/
    services/
    assets/
  public/
  Dockerfile
  nginx.conf
  package.json

docker-compose.yml
pytest.ini
.gitignore
```

## Prerequisites

- Git
- Docker with Docker Compose
- GigaLogy Maira credentials and configured profiles for AI features
- SMTP credentials for email verification, password recovery, and parent reports

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/saifss29/Ict-Foundation-Coach.git
cd Ict-Foundation-Coach
```

### 2. Configure Docker environment variables

Create `.env.docker` in the project root:

```dotenv
POSTGRES_DB=ict_foundation_coach
POSTGRES_USER=ict_coach
POSTGRES_PASSWORD=replace_with_a_unique_database_password
```

### 3. Configure the backend

Create `backend/.env`:

```dotenv
JWT_SECRET_KEY=replace_with_a_long_random_secret

SMTP_HOST=your_smtp_host
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
MAIL_FROM_EMAIL=your_verified_sender_email
MAIL_FROM_NAME=ICT Foundation Coach

FRONTEND_URL=http://localhost:5173

MAIRA_API_KEY=your_maira_api_key
MAIRA_PROJECT_KEY=your_maira_project_key
MAIRA_ASK_URL=your_maira_ask_endpoint
MAIRA_MEMBER_ID=your_maira_member_id
MAIRA_USER_ID=your_maira_user_id
MAIRA_USER_NAME=ICT Foundation Coach

MAIRA_GPT_PROFILE_ID=your_hsc_ict_profile_id
MAIRA_SSC_ICT_PROFILE_ID=your_ssc_ict_profile_id
MAIRA_CALENDAR_GPT_PROFILE_ID=your_calendar_profile_id
```

Replace the placeholders before starting the application. `MAIRA_GPT_PROFILE_ID` selects the HSC ICT profile, while `MAIRA_SSC_ICT_PROFILE_ID` selects the SSC ICT profile.

Docker Compose supplies the backend database URL, Redis connection settings, and frontend URL. Additional Maira profiles may be required for other enabled subjects or AI services.

Real environment files are excluded from Git. Never commit actual passwords, API keys, or tokens.

### 4. Build and start the core services

Run from the project root:

```bash
docker compose --env-file .env.docker up -d --build db redis backend frontend
```

This starts the application without starting the weekly-report worker.

### 5. Apply database migrations

```bash
docker compose --env-file .env.docker exec backend flask --app app db upgrade
```

Migration files are included in the repository to recreate and update the database schema. Existing database records are stored separately.

### 6. Seed the initial topics and practice questions

Run these commands in order:

```bash
docker compose --env-file .env.docker exec backend python seed_topics.py
docker compose --env-file .env.docker exec backend python seed_quiz_questions.py
```

### 7. Open the application

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend health check | http://127.0.0.1:5000/api/health |

Register an account and complete email verification before logging in.

## Weekly Progress Reports

To start the weekly-report worker after configuring the required email and AI settings:

```bash
docker compose --env-file .env.docker up -d weekly-reports
```

To stop it:

```bash
docker compose --env-file .env.docker stop weekly-reports
```

## Running Tests

With the Docker environment configured and the backend image built:

```bash
docker compose --env-file .env.docker run --rm backend python -m pytest -q tests
```

The test fixtures configure an in-memory SQLite database and a test JWT secret.

The test suite covers authentication, tutor conversations, quizzes, classrooms, assignments, exams, progress, messaging, notifications, calendar functionality, and reporting services.

## Useful Commands

Check service status:

```bash
docker compose --env-file .env.docker ps
```

View backend logs:

```bash
docker compose --env-file .env.docker logs -f backend
```

Stop and remove the containers while preserving the database volume:

```bash
docker compose --env-file .env.docker down
```

## Current Limitations

- AI features require valid Maira credentials, profiles, and accessible datasets.
- Email features require a working SMTP configuration.
- Learning coverage depends on the seeded topics and configured AI datasets.
- AI-generated explanations, questions, and feedback can contain mistakes and should be reviewed.
- The included Docker configuration supports local development and demonstration. Public deployment requires separate production configuration.

## Author

**Saif Mohammad Mohibul Islam**

Individual internship project developed for **GigaLogy Ltd**.
