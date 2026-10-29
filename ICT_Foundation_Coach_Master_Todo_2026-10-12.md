# ICT Foundation Coach — Master To-Do List

Updated: 12 October 2026 (Asia/Dhaka). Status reflects Saif's reported tests and manual checks, not an independent repository audit.

## Latest confirmed status — 12 October 2026

- [x] Full backend suite: **1491 passed**, reported by Saif on 12 October. The previous full result was 1446 passed. Historical counts below remain evidence from earlier milestones; do not add targeted counts together.
- [x] Frontend builds and manual checks reported passing after dashboard, navigation, UI and parent-report work.
- [x] Separate student Dashboard, compact maroon Tutor, teacher quiz review/assignment pages, class mistake reports, student weak topics and one-click practice, written/practical tasks, AI reference-answer drafts and AI written-feedback drafts are implemented.
- [x] Teacher quiz history and student assigned-quiz history retain records when removed from the active list. Student removal requires a submitted attempt.
- [x] Redis topic caching and Docker local demo stack are working; PostgreSQL restore was rehearsed into Docker.
- [x] Weekly parent report: real Maira generation, automatic scheduler email delivery through Brevo, parent verification/consent and parent unsubscribe were manually verified.
- [x] New report-related targeted tests: **45 passed**; included in the 1491 full-suite total.
- Current operating state: report worker **stopped** after five-minute testing. The tested parent unsubscribed, so that student's report preference is **Disabled by parent**. Weekly mode was requested; confirm the saved `.env.docker` value before restarting.
- Limits: this is a local demo, not a public deployment or independent repository audit. Complete curriculum coverage, systematic RAG evaluation, official CQ/board-paper generation and final security/mobile/accessibility audits remain pending.

## Historical status - 9 October 2026

- [x] Saif reported **147 passed** for `tests/test_quiz_generator.py` and `tests/test_generated_quizzes.py` after restoring the working generator and aligning the test expectations. This is a targeted run, not a new full-suite total.

- [x] Browser quiz generation reported working after restoration. Preserve this working version; systematic retrieval reliability remains pending.

- At this historical checkpoint, the full backend run was **1257 passed on 8 October**. Earlier counts below are historical evidence, not current full-suite totals.

- [x] One-page final project proposal PDF prepared with Problem Statement, Proposed Solution, Competitive Advantage, Market Opportunity and a proposed Business Model. Saif confirmed sharing the proposal with his mentor; feedback is pending.

- Buyer requirements below are **future enhancements**, not claims of completed features. Existing completed and pending statuses are retained.

- Historical backend suite: 1095 passed (7 October 2026), after account study-level enforcement and test-helper repairs. Saif reported the count; this is not an independent repository run.

- Latest targeted suites: auth 60 passed, topics 25 passed (8 October), standard quizzes 16 passed, generated quizzes 62 passed (8 October), tutor chat 56 passed, progress/recommendations 37 passed, teacher quizzes 102 passed. Do not add targeted counts together.

- Teacher submission review tests: all passed after the database-failure mock was corrected; 137 cases were supplied, but the latest confirmation did not repeat the count.

- Teacher submission review and linked feedback/notification flow: manually confirmed working.

- ICT-only scope confirmed by mentor. Student learning uses the saved SSC/HSC account level. Quiz Practice now offers searchable SSC ICT lessons and supported HSC Number Systems practice.

- Student and teacher quiz learning modes: implemented and reported working; student route suite 39 passed, teacher suite 102 passed, generator mode/context suite 76 passed.

- Tutor learning mode, history restore and database-backed subject/SSC–HSC prompt context: completed; chat/history suite 69 passed.

- Frontend builds and browser mode, history, navigation, topic_slug payload and saved-chat follow-up checks: passed as reported by Saif.

- Completed additions: student feedback-to-teacher direct chat; student registration study level, one-time legacy-account selection, and level-filtered learning access. Completed on 8 October: separate Quiz Practice page, lesson search and selected-topic generation. Also completed on 8 October: offline class exam scheduling, calendar entries, notifications, draft marks, result publication and student own-result views. Pending: systematic retrieval/quality evaluation.

- Final mobile, accessibility, production and security audits remain pending.

## 1. Fixed Project Scope

- Current content: existing HSC Number Systems material plus an SSC ICT starter dataset with 25 lessons. Live tutor/quiz examples work; complete syllabus coverage and systematic grounding are not established.

- Current implementation subject: ICT only, following mentor guidance on 8 October. Other subjects are a future expansion option requested on 9 October (Section 25), not part of the immediate ICT delivery. Existing model support does not establish content readiness.

- Approved learning modes: Exam preparation and Personal growth, for both student self-practice and teacher-assigned practice.

- Personal calendar and Maira activity scheduling already support any subject or activity.

- Frontend: Vue 3 Composition API, Vue Router, Vuex, Vite

- Backend: Flask, SQLAlchemy, Marshmallow, JWT, Alembic

- AI tutor: GigaLogy Maira

- Styling: regular CSS only, no Tailwind

- Every meaningful backend feature must have pytest tests

- Work one file at a time, exact file path first

- Explain security, DB, API, OOP/DRY/KISS/YAGNI fundamentals after backend work

**---**

## 2. Completed Features

### Student learning system

- [x] Student registration, login, logout

- [x] JWT authentication

- [x] Logout token blocklist / revoked-token protection

- [x] Protected API routes

- [x] Session storage auth policy currently used

- [x] Banglish / English Maira tutor response choice

- [x] Topic selection before asking tutor

- [x] Static ICT topic quiz

- [x] Quiz answer validation

- [x] Server-side score calculation

- [x] Quiz explanation/result screen

- [x] Try Again animation

- [x] Progress page

- [x] Completed/not-started topic status

- [x] Latest quiz score

- [x] Next-topic recommendation

- [x] Weakest-topic recommendation

### UI / UX

- [x] Dark/light theme

- [x] Student learning dashboard

- [x] Blue sidebar UI

- [x] Smooth Tutor ↔ Progress page transitions

- [x] Login/Register shared animated screen

- [x] Password lock/unlock show-hide

- [x] Button hover and press animation

- [x] Join-code copy button

- [x] Responsive layouts for main implemented pages

### Teacher–Student system

- [x] User role field: `student` / `teacher`

- [x] Registration account-type choice

- [x] Backend role validation

- [x] Login and `/me` response return role

- [x] Role-based dashboard redirect

- [x] Student route protection

- [x] Teacher route protection

- [x] Student cannot open teacher URLs manually

- [x] Teacher class creation

- [x] Secure 8-character class join code

- [x] Student class join

- [x] Duplicate join protection

- [x] Teacher only sees own classes

- [x] Teacher class analytics

- [x] Student name, email, joined date

- [x] Latest quiz score and percentage

- [x] Total quiz attempts

- [x] Weakest topic

- [x] Last quiz activity

- [x] Class average

- [x] At-risk / Needs attention section

- [x] Student full quiz-attempt history timeline

- [x] Teacher can only view history of students enrolled in own class

### Testing completed

- [x] Auth tests

- [x] Health test

- [x] Chat tests

- [x] Quiz tests

- [x] Progress/recommendation tests

- [x] Role tests

- [x] Classroom create/join/security tests

- [x] Teacher analytics tests

- [x] Student attempt-history tests

- [x] Historical backend suite: 1095 passed; historical progress/recommendations targeted suite: 37 passed. Current full suite: 1491; see latest status.

- [x] Classroom route Pylance warnings fixed

**---**

## 3. Immediate Small Check

- [ ] Sidebar latest expand/shrink and icon alignment final manual test

- [ ] Mobile responsive final manual test for teacher analytics/history pages

- [ ] Check student and teacher routes after a full browser refresh

**---**

## 4. Maira RAG — Initial Implementation Completed

### First verified dataset

- [x] Open Maira Console Web

- [ ] Confirm the exact dataset type in Console (existing verified content is already connected).

- [x] First verified dataset topic: Number Systems.

- [x] Prepare verified Class 11–12 ICT learning content

- [x] Upload/add content to dataset

- [x] Connect dataset with the correct Maira GPT profile

- [x] Test Maira retrieval using Number Systems questions

- [x] Manually test in-scope answers and out-of-scope refusal

- [ ] Evaluate retrieval grounding systematically; correct answers alone do not prove source grounding

### RAG product features

- [ ] Improve tutor prompt for RAG:

   - explain concept

   - small example

   - short recap

   - optional practice prompt

- [ ] Add optional source/citation display in tutor response if Maira API supports it

- [x] Earlier answer-linked quiz CTA was superseded by independent Quiz Practice on 8 October. Tutor follow-ups remain in chat; quiz generation uses an explicitly selected database lesson.

- [x] Upload/train SSC ICT starter material: 25 lessons.

- [ ] Expand and systematically verify ICT coverage beyond the starter lessons.

**---**

## 5. AI-Generated Quiz — Implemented

- [x] Maira generates exactly 5 quiz questions using the configured RAG profile

- [x] Require structured JSON response

- [x] Validate generated quiz JSON on backend

- [x] Correct answer must stay server-side before submission

- [x] Student receives only question + options

- [x] Save generated quiz attempt in database

- [x] Add generated quiz score to progress

- [x] Add generated quiz score to recommendation logic

- [x] Keep static quizzes available alongside generated quizzes

- [ ] Automatic static-quiz fallback is not implemented; generation failure shows an error and permits retry. Existing static quizzes remain separately available.

- [x] Add timeout/error fallback message

- [x] Generated quiz parser, ownership, expiry, scoring, and single-submission tests

- [ ] Automatic fallback tests if automatic fallback is implemented

**---**

## 6. Learning Intelligence — Mastery Implemented

### Mastery Engine — completed

- [x] Shared mastery service used by progress and recommendations.

- [x] Topic statuses: Not started, Needs support, Practicing, Almost mastered, Mastered.

- [x] No attempts → Not started; latest actual score below 50% → Needs support; 50% to below 80% → Practicing.

- [x] Latest score 80%+ → Almost mastered unless the latest two consecutive attempts each reach 80%+, in which case → Mastered.

- [x] Actual score ratios determine status before display rounding; tied timestamps use attempt ID ordering.

- [x] Progress badges and mastery-aware recommendations integrated and manually checked.

- [x] Student isolation, boundaries, ordering and recommendation cases tested; targeted suite 29 passed.

These statuses are app progress indicators, not proof of educational mastery. Concept-level suggestions are deferred until verified subject datasets and question-to-concept mapping are ready.

### Confidence-aware learning

- [ ] Add quiz confidence choice:

   - Not confident

   - Somewhat confident

   - Very confident

- [ ] Save confidence with quiz attempt/answer

- [ ] Detect correct-but-not-confident students

- [ ] Detect wrong-but-very-confident students

- [ ] Give better revision advice

- [ ] Show useful confidence insight to teacher later

### Better teacher insight

- [ ] Improve at-risk rules:

   - no quiz attempts

   - repeated low score

   - declining score

   - inactivity for a selected time period

- [ ] Teacher intervention queue:

   - student name

   - risk reason

   - suggested topic to revise

- [ ] Topic-wise class weakness view

- [ ] Class comparison / overall analytics

- [ ] Weekly teacher performance report

**---**

## 7. Student Productivity Features

- [ ] Student quiz-attempt history in own dashboard

- [x] Save chat conversation history in database

- [x] Student can read old tutor conversations

- [x] New chat and previous-conversation selection

- [x] History survives logout/login

- [x] History ownership, teacher restrictions, and pagination tests

- [x] Vuex tutor state preserves chat when navigating between pages

- [ ] Study planner

- [x] Personal calendar-based study scheduling through manual events or Maira.

- [ ] Automatic multi-event study-plan generation (separate future extension).

- [ ] Quiz retry reminder

- [ ] Learning streak

- [x] AI weekly progress summary delivered to verified, consenting parents; see Section 31. A separate student weekly-summary screen is not implemented.

- [ ] Speech-to-text tutor input

   - first use browser Web Speech API

   - support Bangla/English where available

**---**

## 8. Private Book / PDF RAG — Advanced Later Feature

- [ ] Student can upload personal PDF/note/book

- [ ] File type and file size validation

- [ ] Secure private file storage

- [ ] Extract text from uploaded material

- [ ] Split text into chunks

- [ ] Add chunks to vector/RAG retrieval system

- [ ] “Ask from my uploaded book” tutor mode

- [ ] Show retrieved page/source citation

- [ ] Generate summary from uploaded material

- [ ] Generate quiz from uploaded material

- [ ] Ensure one student cannot access another student’s document

**---**

## 9. Account and Security Features

### Password security

- [x] Password strength meter: Weak / Medium / Strong

- [x] Backend strong-password policy

- [x] Reject weak password on registration

- [x] Add weak-password pytest tests

### Forgot password

- [x] Forgot Password page

- [x] Secure reset token

- [x] Reset token expiry

- [x] Password reset endpoint

- [x] Reset-password tests

- [x] Reset-password frontend with lock/unlock and strength estimate

- [x] Hash reset tokens, expire links, and enforce single use

- [x] Invalidate old JWTs after password reset using user token_version

### Email verification

- [x] Choose email service/provider first

- [x] Use Brevo SMTP through the application email service; real inbox delivery tested

- [x] Send verification email after registration

- [x] Verification link with expiry

- [x] Block login until verified

- [x] Resend verification email

- [x] Verification/resend/expiry tests

- [x] Registration confirmation and resend option in AuthView

- [x] VerifyEmailView and public /verify-email route

- [x] Verification page uses existing theme and hides sidebar

- [x] Real registration → email → verification → login flow manually confirmed

### General security

- [ ] Final session policy decision:

   - should a new browser tab stay logged in?

   - should browser close log out?

- [x] Rate limiting for login, registration, forgot-password, and resend-verification; 429 responses tested.

- [ ] Rate limiting for tutor chat and AI quiz generation.

- [x] Docker services use Redis for shared rate-limit storage. Local non-Docker configuration may still default to memory; public production deployment remains pending.

- [ ] Production CORS configuration

- [ ] Final environment-variable/secrets audit

- [ ] Friendly JWT expiry handling everywhere

**---**

## 10. Remaining Backend Tests

- [x] Topics list and paginated lesson-search tests: account-level filtering, teacher access, missing level, query override and search cases; 25 passed on 8 October.

- [ ] Chat missing-Maira-configuration test

- [ ] Chat generic request failure test

- [x] Chat empty Maira response test

- [ ] Quiz topic-not-found test

- [ ] Quiz no-questions-found test

- [ ] Multiple quiz attempts affect progress correctly test

- [x] No-topic recommendation test

- [x] Mastery Engine tests, including boundaries and student isolation

- [x] Generated quiz tests when feature is built

- [x] Password security tests when feature is built

**---**

## 11. Cleanup and Delivery

- [ ] Final AuthView layout verification: content-driven panel-height CSS fix supplied for clipped login link; explicit post-fix browser confirmation still needed. Registration payload inspected and correctly sends level only for students. Earlier generic registration error was not conclusively diagnosed.

- [ ] Delete unused old files only after confirmation:

   - `LoginView.vue`

   - `RegisterView.vue`

- [ ] Final frontend loading/error/empty-state audit

- [ ] Final mobile audit

- [ ] API documentation

- [ ] README:

   - setup instructions

   - `.env` variable names only, no secrets

   - frontend/backend run commands

   - migration commands

   - test commands

   - architecture overview

- [ ] Add screenshots/demo data

- [x] Dockerize frontend/backend with PostgreSQL and Redis; dedicated weekly-report worker added. See Section 30.

- [ ] Add GitHub Actions CI to run pytest

- [ ] Deploy frontend, backend, and PostgreSQL later

- [ ] Final project demo and presentation

**---**

## 12. Final Presentation Talking Points

- [ ] Problem in Bangladesh education context

- [ ] Why ICT-only learning support with account-based study contexts

- [ ] Banglish AI tutor

- [ ] Maira RAG with verified content

- [ ] Existing static quizzes and independent AI-generated Quiz Practice

- [ ] Student progress and mastery

- [ ] Teacher–student class analytics

- [ ] JWT and role-based authorization

- [ ] Database design and secure ownership checks

- [ ] Testing: pytest coverage

- [ ] DRY, KISS, YAGNI, SOLID where actually used

- [ ] Future roadmap: private document RAG, planner, speech-to-text

## 13. Product Thinking — Discussion, Not Implemented Features

- [ ] Validate the specific student and teacher problem with real users.

- [ ] Explore concept-level learning gaps, targeted practice, and follow-up assessment.

- [ ] Explore actionable teacher insights and measure learning improvement in a small pilot.

- Current product scope is ICT only, with Exam preparation and Personal growth modes. HSC Number Systems and an SSC starter dataset are available; broader curriculum coverage remains to be evaluated.

- Subject/level infrastructure remains for compatibility. Additional subjects are deferred beyond the current ICT delivery; the future expansion requirements are recorded in Section 25.

- Mastery thresholds above are implemented app rules, not proof of mastery.

- Remaining test items above need a current test-file audit before marking completed; the passing total alone does not prove each specific case exists.

## 14. Teacher–Student Communication and Class Membership

Completed communication behavior is visible in current routes; older unchecked messaging sub-items below need a current source/UI audit before their exact details are marked complete. Do not rebuild working messaging.

### Class details and membership

- [x] Student can join a class using its join code (existing feature).

- [x] Show joined class name and teacher name.

- [ ] Show the student's joined date in the student class panel.

- [x] Add a student leave-class action with confirmation.

- [x] Keep the student's own learning and quiz history after leaving a class.

- [x] Define and enforce teacher access to former members' records.

- [x] Add ownership, membership, leave, and permission tests.

### Contact teacher and two-way messaging

- [ ] Add a Message teacher action in joined class details.

- [ ] Let students message teachers of their joined classes.

- [ ] Let teachers initiate messages to enrolled students and reply.

- [ ] Save conversations and messages with timestamps.

- [ ] Show unread message counts and read status.

- [ ] Enforce participant and class-membership permissions on the backend.

- [ ] Define messaging access after a student leaves a class.

- [ ] Add messaging validation, authorization, and history tests.

- Contact teacher and teacher–student chat are one integrated feature; personal phone/email exposure is not required.

### Direct teacher feedback

- [x] Let teachers send general feedback or feedback linked to a quiz attempt.

- [ ] Support an independent topic link if needed beyond the linked quiz attempt.

- [x] Students can view received feedback, its author, class, date, and linked attempt ID.

- [x] Teacher feedback form and paginated sent-feedback list.

- [x] Student feedback panel with refresh and pagination; persistence after refresh manually confirmed.

- [x] Show feedback author and timestamp.

- [ ] Show follow-up practice/improvement after feedback.

- [x] Add feedback permission and persistence tests.

- Teacher feedback is implemented, including sending attempt-linked feedback directly from submission review; student feedback and notifications manually confirmed.

### In-app notifications

- [x] Notify students of new teacher feedback.

- [ ] Notify teachers/students of new messages.

- [x] Show unread notification count and mark-as-read action.

- [x] Personal calendar reminders delivered as in-app notifications by a background command.

- [ ] Enforce notification ownership and add tests.

- [x] Personal reminder timing and local background delivery defined; timer runs every minute.

- [ ] Production reminder worker deployment and official quiz reminder rules.

### AI learning suggestions

- [x] Basic next-unattempted/weakest-topic recommendations already exist.

- [ ] Identify specific weak concepts using quiz-answer evidence.

- [ ] Suggest targeted explanations, practice, and revision.

- [ ] Assess improvement with follow-up questions.

- [ ] Avoid treating a chat question alone as proof of weakness.

- [ ] Test the recommendation rules and evaluate suggestion quality.

### Additional proposed ideas — Not Yet Committed

- [ ] Consider class announcements visible to all enrolled students.

- Unread/read status and feedback follow-up above remain planned, but details should be finalized when building their parent features.

### Existing account feature

- [x] Email verification: registration email, expiring single-use link, resend, login blocking, frontend verification page, and tests.

## 15. Updated Build Order

Completed milestones: calendar/Maira/reminders, mastery/recommendations, teacher submission review with linked feedback, student/teacher quiz modes, and tutor mode plus database-backed subject/exam context.

Current order after 8 October:

1. Keep the completed feedback-to-chat, account-level separation and independent Quiz Practice flows working.

2. Final integration verification recorded: 1257 passed and frontend build passed. Next audit live retrieval reliability separately from mocked tests.

3. Offline exams, publication, calendar entries and student notifications completed (Section 19); retain their tested behavior.

4. Expand verified ICT content and improve live generation quality incrementally.

5. Final audits, documentation, CI and deployment when scheduled.

Do not reopen completed personal calendar work for optional refinements. Offline exam calendar integration is completed; see Section 19 for deferred extensions. Assignment rescheduling/cancellation, durable browser retry state and configurable personal reminder UI remain deferred.

Work one file at a time. Preserve auth, tutor, quizzes, progress and messaging. Read current files before replacements, test meaningful backend changes, build and manually check frontend changes.

## 16. Calendar and Maira Event Assistant — Current Status

### Personal calendar for both roles

- [x] Teacher and student personal study, teaching and other activity events.

- [x] Title, optional description, start/end time and timezone validation.

- [x] Owner-only create, list, view, update and delete APIs.

- [x] Personal calendar privacy; class membership does not expose private events.

- [x] Shared month/date view and selected-day event list.

- [x] Manual create/edit/delete flow, separate from Maira controls.

- [x] Loading/error/empty states and existing theme styling with regular CSS.

- [x] UTC timestamp storage and local timezone display.

- [x] Bounded visible date ranges and pagination for all matching entries.

- [x] Both roles' calendar use manually confirmed by Saif.

- [ ] Final comprehensive mobile/accessibility audit, together with the final app audit.

### Assigned quiz calendar integration

- [x] Student entries use saved assignment recipients.

- [x] Teacher entries use teacher-owned assignments.

- [x] Display availability, deadline, time limit and review time.

- [x] Navigate to existing student assignment or teacher quiz/results pages.

- [x] QuizAssignment remains the authoritative schedule; no independently editable personal copy.

- [x] Personal editing controls cannot change official quiz schedules.

- [x] Preserve saved recipient visibility rather than automatically assigning later joins.

- [x] Assignment creation saves recipient notifications atomically.

- [ ] Official rescheduling/cancellation API and rules for active/submitted attempts — deferred.

- [ ] Recipient notifications for official schedule changes/cancellation — deferred with that feature.

- [x] Offline class exams appear as authoritative read-only calendar entries for saved recipients and owning teachers, with schedule/publication notifications; see Section 19. The exam takes place outside the app.

### Maira personal event assistance

- [x] Both roles can create personal events using natural-language requests.

- [x] Any subject/activity is supported; calendar assistance is not ICT-only.

- [x] Dedicated calendar GPT profile, separate from the verified-content tutor profile.

- [x] Structured proposal output validated by the backend.

- [x] Missing or ambiguous information triggers clarification.

- [x] Update targets a selected owned event and checks its version.

- [x] Authenticated user ownership enforced; AI does not choose an owner.

- [x] Frontend automatically saves valid proposals through the existing calendar CRUD API, as requested by Saif.

- [x] Manual and Maira panels are separate; user chooses either flow.

- [x] Stale updates are rejected rather than silently overwriting newer changes.

- [x] Create requests can include a UUID request_id; backend receipts prevent duplicate creates for a repeated key and payload.

- [x] Receipt, event and creation notification are committed together.

- [x] Different payload with the same request key returns a conflict.

- [x] Frontend reuses a pending create request while its flow remains open.

- [x] Manual and Maira normal creation manually confirmed.

- [x] Manual offline → online retry manually confirmed to create one event.

- [ ] Maira failed-save Retry save path has not been separately manually verified.

- [ ] Persist pending request keys across reload/closed forms — optional and explicitly deferred.

- [x] Maira failures do not mutate saved events; manual calendar remains available.

- [x] Personal Maira assistance does not authorize official assignment changes.

The earlier preview/explicit acceptance plan was replaced by Saif's preferred automatic save flow. Do not reintroduce it without a new product decision. Current retry protection is limited to a retained request key; a new key can create another event with the same details.

### Reminders

- [x] Personal event reminder fields and migration.

- [x] Background Flask command: send-calendar-reminders.

- [x] Due reminders create in-app notifications and record delivery in one transaction.

- [x] Repeated processing avoids sending the same reminder again.

- [x] Local systemd service/timer enabled; runs every minute.

- [x] Actual reminder notification and repeated command behavior manually confirmed.

- [x] Background delivery does not depend on an open browser tab.

- [ ] User-facing reminder lead-time/off controls — future improvement.

- [ ] Official assignment reminders — separate future feature.

- [ ] Production worker deployment — delivery work.

Local reminders require the computer/session timer and database to be available. Current delivery is in-app, not browser push, email or SMS.

### Test evidence and closure

- [x] Latest reported calendar route test run: 105 passed.

- [x] Calendar assistant schema tests: 32 passed.

- [x] Calendar assistant service tests: 51 passed (parser and request handling).

- [x] Reminder service tests: 10 passed.

- [x] CRUD ownership, validation, timezone/range behavior and official assignment visibility checks.

- [x] AI malformed output, clarification, ownership, stale updates and failure checks.

- [x] Create receipt replay, normalized payloads, user isolation, invalid keys, rollback and deleted-event replay tests.

- [x] Frontend build passed after create retry integration.

- [ ] Actual concurrent PostgreSQL duplicate-request race has not been separately exercised.

These are targeted runs, not an updated full-suite total; do not add their counts together. Latest reported backend suite is 1095 passed (7 October 2026). The current calendar milestone is closed; optional work above remains deferred.

## 17. Teacher-assigned AI Quizzes — Confirmed Progress

- [x] Generate AI quizzes from verified Number Systems ICT material.

- [x] Teacher chooses 1–20 questions and Banglish/English response language.

- [x] Review/edit questions, options, correct answers and explanations before publishing.

- [x] Publish a saved draft; published questions are read-only.

- [x] Assign to all enrolled students or selected students with a saved recipient snapshot.

- [x] Configure availability, deadline, time limit, allowed attempts and review time.

- [x] Save assignment, recipients and notifications together.

- [x] Student assigned quiz list and protected student route.

- [x] Start/resume timed attempts; save answers, enforce attempt limits and submit with server-side grading.

- [x] Submitted assignment scores feed existing QuizAttempt/progress records.

- [x] Correct answers/explanations hidden before the permitted student review time.

- [x] Student attempt history and saved results after refresh.

- [x] Student answer review manually confirmed using a new quiz.

- [x] Teacher results API, paginated recipients, per-attempt scores/status and best submitted score.

- [x] Teacher results frontend manually confirmed for both tested quizzes.

- [x] Assignment tests cover creation/access, timed attempts, secrecy, student review/history, teacher results and teacher submission review; latest teacher-review check reported all passed.

- [ ] Show assignment form errors beside the form; invalid review time previously appeared to do nothing because the error was above the visible area.

- [x] Teacher question-by-question submission review showing selected, correct and unanswered answers with explanations; manually confirmed.

- [x] Both quiz/class ownership and saved recipient checks; students cannot access teacher review, and teachers can review submitted work before student review_at.

- [x] Review response exposes integer quiz_attempt_id; results review sends attempt-linked feedback through the existing feedback API.

- [x] Student feedback and notification delivery manually confirmed. Existing feedback API still requires current class membership; historical review remains accessible to saved recipients after leaving.

- [ ] Persist immutable question/answer snapshots for historical submissions. Current published quiz immutability and saved answers are not a separate full question snapshot.

- [ ] Background finalization of expired attempts; current result listing marks expired pending attempts without grading them.

- [ ] Notification deep links/shared assignment links.

- [x] Calendar integration, as specified in Section 16.

## 18. Confirmed Learning Flow — Exam Preparation and Personal Growth

### Scope and distinction

- Learning subject: ICT only. Math/English expansion is no longer in the current scope.

- Exam preparation uses the saved account study level and a supported ICT lesson. Current MCQs are concept practice; full board patterns are not implemented.

- Personal growth: improve concepts and practical skills through suitable MCQs, problem solving, written exercises or real-life tasks. Board-style CQ is not mandatory.

- The same topic can support both modes. Subject/academic level belong to the topic; learning_mode belongs to the quiz/activity.

- Additional subject content is deferred outside the current ICT-only scope.

- Confirm syllabus, paper/course distinctions and current exam patterns before implementing exam-format generation. This roadmap does not certify any year's marks distribution.

### Student self-practice

1. Use the saved study level and choose a learning mode.

2. For tutoring, ask questions and continue follow-ups in Tutor. For quizzes, open Quiz Practice, search and select an available lesson.

3. Generate five selected-lesson MCQs in Quiz Practice without requiring a chat or teacher assignment.

4. Complete practice and view results, explanations and progress using the applicable flow.

5. Plan learning activities manually or through Maira in the existing personal calendar.

### Teacher-assigned practice

1. Choose ICT, mode, relevant level/topic and a supported question type/count.

2. Generate, review/edit and publish the practice.

3. Assign to all current enrolled students or selected students with availability, deadline, time limit, attempts and review time.

4. Students receive notifications and calendar entries, complete practice and view results according to review rules.

5. Teacher reviews submissions and sends feedback through the implemented results review flow.

### Implemented infrastructure

- [x] Topic.subject: ict/math/english; Topic.academic_level: ssc/hsc, with database constraints and indexes.

- [x] Existing topics default to ict/hsc; PostgreSQL migration 0907cc922058, parent 774ecd518e43, applied and reported working.

- [x] Topics API returns subject and academic_level; stable display_order/id ordering.

- [x] Teacher generation subject/level selectors filter supported topics and clear stale selections.

- [x] Student Quiz Practice supports seeded SSC ICT lessons and HSC Number Systems; unsupported topics remain unavailable. Teacher generation expansion has not been separately verified.

- [x] Historical full suite after topic infrastructure: 918 passed; historical full suite after modes and tutor context: 1012 passed. Latest full suite is 1095 passed, reported 7 October; no post-8-October full run is recorded.

### Completed mode and tutor context work

- [x] GeneratedQuiz and TeacherQuiz store learning_mode with default personal_growth; accepted modes are exam_preparation and personal_growth.

- [x] Student generated-quiz route validates mode, passes mode plus database topic subject/level to the generator, saves mode and returns it on create/GET.

- [x] Student route tests verify mode persistence, defaults, invalid input and answer secrecy; 39 passed reported.

- [x] Generator mode/context tests: 76 passed reported.

- [x] Teacher create schema accepts/validates learning_mode; invalid input is rejected before generation.

- [x] Teacher generation passes database topic subject/level and selected mode, including supported question-count branches.

- [x] Teacher saved mode is returned and preserved across reload, listing, editing and publishing; teacher tests 102 passed reported.

- [x] Student and teacher mode selection and saved-mode display built and manually confirmed working.

- [x] ChatConversation stores learning_mode with default and validation; chat mode migration 9819838e7684, parent 61ec99df52bd, reviewed to include the check constraint and reported applied.

- [x] POST /api/chat validates mode, includes mode-specific tutoring instructions, saves mode and returns it.

- [x] Existing conversations reject topic/language/mode changes with 409; same-mode follow-up is supported.

- [x] Chat history list/detail return the saved mode.

- [x] Vuex tutor state stores learningMode; HomeView sends mode, starts a new chat on mode change and restores mode when opening history.

- [x] Topic slug is validated and resolved by the backend; unknown slugs and title mismatches are rejected before Maira calls.

- [x] Tutor subject comes from the selected database topic; topic level must match the account. Requests omitting topic_slug resolve known titles and enforce the same check; general-chat level comes from the account rather than a fixed HSC fallback.

- [x] HomeView sends topic_slug; browser payload and saved-chat follow-up manually checked.

- [x] Chat/history tests cover modes, defaults, invalid inputs, persistence and ICT/Math/English × SSC/HSC prompt context; 69 passed reported.

- [x] Historical full backend suite 1012 passed; frontend build passed; browser mode selection, history restore, page navigation and follow-up confirmed by Saif.

Quiz mode integration is reported complete. Earlier mode migration identifiers are not recorded here; verify current migration files before future schema work. The later practice_topic migration is recorded in Section 24.

### Remaining ICT learning expansion

- [x] Account-based SSC/HSC separation — Section 21.

- [x] Independent, searchable lesson selection and quiz practice — Section 24.

- [x] SSC/HSC ICT profile selection configured; example live checks reported working — Section 22.

- [ ] Systematically evaluate source grounding, unsupported-topic refusal and retrieval reliability in both profiles.

- [ ] Expand verified ICT lessons incrementally and enable generation only for supported material.

- [ ] Evaluate lesson-level progress reporting for historical quizzes stored under broad subject topics; practice_topic is a saved label, not a separate mastery entity.

- [ ] Audit assignment recipient rules and historical chat access against account level.

SSC/HSC are study/exam contexts; ICT is the current learning subject. Existing subject enum values do not imply supported product content.

Student-generated MCQs remain five questions; teacher MCQs support 1–20. Full board patterns, CQ, written-answer grading and practical-task grading are not implemented.

## 19. Offline Term/Final Exams — Completed 8 October

A teacher conducts the exam outside the app, then records and publishes results. ICT is the current product subject; there is no separate exam subject field or in-app exam-taking flow.

- [x] ClassExam and ClassExamResult models, constraints and indexes; PostgreSQL migration `406133132cae`, parent `ffa2103d444d`, applied as reported.

- [x] Teacher creates an exam for an owned class with title, instructions, total marks, start/end and timezone. Empty classes are rejected.

- [x] Current enrolled students are saved as exam recipients at creation. Later joins are not automatically assigned; leaving retains saved exam/result visibility.

- [x] Schedule notification and recipient records save atomically with the exam.

- [x] Official exam entries appear in teacher/student calendars with date-range overlap and UTC conversion; personal edit/delete controls cannot modify them.

- [x] Teacher enters decimal marks or Absent, saves partial draft batches and reloads results with pagination.

- [x] Validate marks from zero through total marks, at most two decimal places; absent students have no marks. Missing present-student marks block publication.

- [x] Publish complete results atomically and notify saved recipients. Repeated publication does not duplicate notifications.

- [x] Published results are read-only; drafts are hidden from students. Class ownership, role and recipient privacy are enforced.

- [x] TeacherClassExams integrated into teacher class analytics; student-only Exam Results page, route and sidebar show only the student's published result or Results pending.

- [x] Models 10 passed, schemas 42 passed, class exam routes 83 passed reported. Tests include authorization, persistence, marks, publication, recipient access, timezone overlap and rollback.

- [x] Frontend build and teacher scheduling/marks/publication, student calendar and own-result browser checks confirmed by Saif.

- [x] Final full backend run: 1257 passed, 8 October 2026. Targeted counts are not added together.

### Deferred extensions and verification limits

- [ ] Exam editing/cancellation and notifications for schedule changes.

- [ ] Published-result correction workflow.

- [ ] Timed exam reminders; current exam notifications occur at scheduling and publication. Personal reminder infrastructure remains separate.

- [ ] Creation request idempotency beyond the frontend busy guard.

- [ ] Exam/result notification deep links.

- [ ] PostgreSQL concurrency verification and comprehensive mobile/accessibility review.

No AI paper generation, online submissions, automated grading or contribution to quiz mastery is implemented for offline exams.

## 20. Feedback Page → Direct Chat — Student Flow Completed

- [x] Student feedback cards open direct chat with the feedback author using teacher_id.

- [x] Reuse POST /api/messages/conversations and the existing MessagesView route/UI.

- [x] Per-card pending/error handling and authentication/account-change guards supplied.

- [x] Saif manually confirmed opening chat and sending/receiving messages.

- [ ] Separate teacher-side feedback-card navigation, if desired; not verified as implemented.

Existing direct-message permissions remain authoritative. Do not infer additional class-membership requirements or mark every older Section 14 sub-item complete from this shortcut alone.

## 21. Account-Based SSC/HSC Learning Separation — Implemented

### Completed account and backend behavior

- [x] Student registration requires Study level: SSC or HSC only. Teachers do not select a level and retain null academic_level.

- [x] User model stores nullable academic_level with valid-level and teacher-null constraints.

- [x] Migration 9b4549c75c26, parent 9819838e7684, reviewed and reported applied.

- [x] Registration validates role/level combinations; register/login/profile serialization returns saved level.

- [x] PATCH /api/auth/me/academic-level lets an older student account choose once; same-value retry allowed, switching saved level rejected. Atomic conditional update used.

- [x] AuthView sends level only for student registration; Vuex retains the complete returned user.

- [x] HomeView refreshes profile, offers legacy-account level selection when missing, and loads learning content using the saved level.

- [x] Topics API filters students by saved level; teachers can view both levels.

- [x] Standard quiz load/submit and generated quiz create/load/submit enforce account/topic level match.

- [x] Tutor checks saved level before Maira; validates matching database topic through slug or known title, including continued conversations.

- [x] General tutor chat uses account level; this does not establish isolated retrieval datasets.

- [x] Progress and recommendations filter both topics and attempts by account level; summary and mastery use only eligible topics.

- [x] Required-level registration test helpers repaired across calendar, history, classes, messages, notifications, password reset, assignments, feedback and teacher quiz tests.

- [x] Reported latest backend suite: 1257 passed (8 October); frontend build reported passed.

### Manual checks confirmed by Saif

- [x] HSC student Home topic list, tutor reply/follow-up, normal quiz score and matching progress score.

- [x] Historical 7 October check: SSC Home was empty under the HSC-only seed. Superseded on 8 October by seeded SSC ICT content and Quiz Practice.

- [x] SSC opening the HSC Number Systems quiz URL displays no available topic/questions.

- [x] Historical 7 October SSC logout/login check passed; the empty-content expectation is superseded by the SSC seed.

- [x] Teacher dashboard/quizzes open.

- [ ] Independently confirm teacher level prompt absence, HSC refresh/login persistence and complete mobile behavior; not individually reported in this final check sequence.

### Remaining scope

- [x] Add independent ICT Quiz Practice navigation and account-level lesson search.

- [x] Seed 25 SSC ICT lessons; seed run reported 25 topic(s) created.

- [ ] Expand verified ICT coverage; no Math/English navigation is planned.

- [ ] Audit teacher-assignment recipient policy against topic level before claiming all assigned-content paths are isolated.

- [ ] Audit old chat-history visibility separately; tutor follow-up checks do not filter the history API by themselves.

- [ ] Distinct full visual designs for SSC/HSC, if wanted; current approach shares the dashboard and separates its learning content.

Study level is selected on the student account, not on each login. SSC/HSC are exam contexts; ICT is the current learning subject. Exam Preparation/Personal Growth remain separate activity modes.

## 22. Separate ICT Datasets and Profiles — Configured; Evaluation Pending

- [x] Retain the existing HSC ICT/Number Systems profile: `a9ee4fa2-c165-477f-91e7-68fbef954c5a`.

- [x] Train the SSC ICT starter dataset with 25 lessons and connect profile `b8a245fc-323c-44d0-aa07-d6ffe674b109`.

- [x] Configure backend SSC/HSC ICT profile selection using the saved account/database topic context; the client does not choose arbitrary profile IDs.

- [x] Reported live examples: HSC Binary 101 explanations and quizzes; SSC Save/Save As explanations and selected-topic quizzes.

- [x] Keep the calendar assistant profile separate from learning retrieval.

- [ ] Record and review provenance for all lesson content, including textbook-aligned versus optional foundation material.

- [ ] Systematically check source grounding, profile isolation and unsupported-topic behavior. Correct examples and passing prompt tests alone do not establish these properties.

- [ ] Assess intermittent retrieval refusals, timeouts and malformed quiz output. Strict validation continues to reject missing answer fields and invalid JSON; a successful retry does not prove reliability.

- [ ] Expand supported lessons only after content and live retrieval checks.

Math/English datasets are outside the current implementation scope; future expansion is recorded in Section 25. The SSC starter dataset is not a claim of complete syllabus coverage. The Console and backend use different request paths; their behavior must be evaluated separately.

## 23. Next Work Order — Updated 9 October Evening

1. Completed milestone: Saif reported 1301 backend tests passed, frontend build passed, and manual Learning Assignments create/submit/review/result/notification flows working on separate teacher/student pages.

2. Code and PostgreSQL backups have passed archive/readability checks; see Section 27. Actual restore rehearsal remains pending.

3. Evaluate ICT retrieval and quiz reliability through the actual application for both profiles; preserve the working generator while recording unsupported-topic, timeout and malformed-output cases.

4. Audit unsupported-subject handling, historical access and teacher-assignment study-level policy before making stronger isolation claims.

5. Complete source provenance, mobile/accessibility and error/loading audits, then demo/documentation preparation. File uploads, AI written drafts and advanced assignment features remain deferred.

Read current files before replacements. Work one file at a time; provide full copy/paste files when changes are extensive. Test affected files during repairs; use the full suite at milestones.

## 24. Independent Quiz Practice — Completed 8 October

### Backend and lesson selection

- [x] Add nullable `GeneratedQuiz.practice_topic` (150 characters) for the saved practice label.

- [x] Apply PostgreSQL migration `ffa2103d444d`, parent `9b4549c75c26`.

- [x] Add authenticated `/api/topics/search`: ICT lessons filtered by the student's saved level, title search, 20-item pages and load-more pagination; broad SSC/HSC subject cards are excluded.

- [x] Keep `/api/topics` compatibility and existing topics; seed 25 SSC lessons without deleting older HSC records.

- [x] Generate from the selected database lesson title, subject, level, language and mode. This frontend flow sends no conversation_id or chat discussion.

- [x] Validate supported lessons and level access before generation; preserve ownership, expiry, answer secrecy and server-side grading.

- [x] Save selected practice label/mode and return them on reload.

### Frontend and navigation

- [x] Add student-only `/practice` (`quiz-practice`) and `QuizPracticeView.vue`.

- [x] Add sidebar Quiz Practice navigation; searchable topics avoid scrolling a large dropdown.

- [x] Keep independent language/mode selectors and loading/error/empty states.

- [x] Remove quiz selection/generation controls from HomeView; Tutor retains its conversations, follow-ups, history and Vuex state.

- [x] Update QuizView to show selected practice title, return to Quiz Practice and provide Ask Maira navigation to Tutor.

- [x] Preserve legacy static quiz retry behavior; generated practice does not show unsupported standard/new-AI controls.

- [x] User reported frontend build passing and browser flow working: search/select, generate, submit/score and return navigation.

### Latest evidence and limits

| Check | Reported result | Date |

| --- | --- | --- |

| Quiz generator suite | 76 passed | 8 October 2026 |

| Topics/search suite | 25 passed | 8 October 2026 |

| Generated quiz suite | 62 passed | 8 October 2026 |

| Frontend build | Passed | 8 October 2026 |

| Separate Tutor/Quiz Practice browser flow | Working, confirmed by Saif | 8 October 2026 |

| Latest full backend suite | 1257 passed after integration | 8 October 2026 |

- [x] Full backend result after the 8 October integration changes: 1257 passed.

- [ ] Final comprehensive mobile/accessibility audit.

- [ ] Chapter filtering, automatic dataset-to-topic import and full syllabus coverage are not implemented.

Quiz generation now follows the explicitly selected lesson, including after a vague tutor follow-up such as “explain more”; chat wording no longer determines the quiz topic. Backend compatibility with earlier conversation-based requests may remain, but the new page does not use it.

**---**

## 25. Buyer Requirements and Future Enhancements - Added 9 October 2026

### Scope and implementation rules

Current delivery remains SSC/HSC ICT. This roadmap records future options; it does not commit all features to the internship deadline. Implement one approved feature at a time, inspect current code first, preserve working flows, and verify affected backend tests and frontend behavior before continuing.

Existing features to reuse: mastery statuses, weakest-topic recommendations, class analytics/at-risk views, teacher quiz draft review/edit/publish, classes, feedback, calendar, notifications and offline exam results. Do not rebuild these as new features.

### Priority 1 - Content trust and actionable learning support

#### 1. Source references and content validation

Buyer need: students and teachers can check which learning material supports an explanation.

- [ ] Extend the citation work in Sections 4, 8 and 22: inspect actual Maira response fields before choosing a display format.

- [ ] Show available lesson/book references and page numbers only when returned or reliably mapped; never invent citations.

- [ ] Distinguish textbook-aligned material from optional foundation lessons.

- [ ] Check whether returned references actually support tutor answers and quiz explanations; displaying a reference alone does not prove grounding.

- [ ] Test missing-reference behavior and preserve usable responses when citation data is unavailable.

#### 2. Detailed weak-topic report

Buyer need: a teacher can identify students who repeatedly struggle and decide what to teach again.

- [ ] Extend Section 6's topic-wise class weakness view and Section 14's concept-level suggestions using saved quiz evidence.

- [ ] Audit lesson identity first: historical broad topic IDs and `practice_topic` labels must not be treated as interchangeable mastery entities.

- [ ] Show repeated mistakes, recent score trends, attempt counts and the reason a student needs attention.

- [ ] Add verified question-to-concept mapping before claiming concept-level weakness.

- [ ] Keep reports restricted to authorized teachers and eligible students; test class ownership and membership/history rules.

- [ ] Confirm reports remain useful with few attempts; do not label a student weak from one chat question.

#### 3. Personalised revision plan

Buyer need: a student knows which lesson to revise and what practice to do next.

- [ ] Extend existing recommendations rather than replace the mastery service.

- [ ] Suggest a short sequence of supported lessons and practice based on quiz evidence, with a clear reason for each suggestion.

- [ ] Let students review a suggested plan before adding study events; keep existing personal calendar behavior intact.

- [ ] Record plan completion and offer follow-up practice to assess progress.

- [ ] Provide a useful starting plan when no quiz history exists; evaluate suggestions with students/teachers before claiming learning improvement.

#### 4. Teacher approval records

Buyer need: a teacher can take responsibility for content used in a class.

Already implemented: teacher-generated quiz drafts can be reviewed, edited and published (Section 17).

- [ ] Audit the existing publish workflow before adding approval fields or states.

- [ ] If needed, record reviewer, approval time and the approved content version.

- [ ] Define whether approved lesson material can be shared across classes; restrict editing and publication to authorized users.

- [ ] Keep AI drafts distinct from approved content; test version changes and published-content rules.

### Priority 2 - Stronger practice and manageable content

#### 5. Difficulty-based practice

Buyer need: practice is appropriate for a beginner and can become more challenging as the student improves.

- [ ] Define easy/medium/hard criteria with teachers; use understanding and application requirements, not labels alone.

- [ ] Add difficulty selection and persistence to the relevant generation, quiz and result flows.

- [ ] Generate questions only from supported lesson material at the selected study level.

- [ ] Evaluate question difficulty and correctness manually; adaptive recommendations should follow verified rules and retain student choice.

- [ ] Test defaults and compatibility so existing quizzes still load, score and review correctly.

#### 6. Content management panel

Buyer need: an authorized content manager can maintain supported lessons without editing seed scripts manually.

- [ ] Define content-manager permissions and inspect current topic/profile configuration before changing the schema.

- [ ] Add search, pagination and create/update/availability controls for lessons, study levels, chapters and provenance.

- [ ] Track content validation and retrieval checks separately from Console training status.

- [ ] Make unavailable or unverified lessons unavailable for new generation while preserving historical quiz records.

- [ ] Confirm supported Maira dataset/profile operations before promising automatic upload/training from the panel.

- [ ] Keep API/project keys on the backend; add change history, validation and permission tests.

#### 7. Practical ICT assignments

Buyer need: students demonstrate skills beyond choosing MCQ answers.

- [x] Add manually authored written/practical ICT tasks with instructions; students submit text/code. Baseline completed and checked on 9 October; see Section 27. Document/spreadsheet file uploads remain pending.

- [x] Implement text/code submission, availability/deadline, total marks and manual teacher feedback. Structured marking rubrics remain pending.

- [ ] Add secure upload limits, private storage and student/class ownership checks if file submission is used.

- [x] Provide the saved single submission, marks and feedback to the student, retained after refresh. Multiple-version submission history remains pending.

- [x] Keep practical-task results separate from MCQ mastery. Manual teacher grading is implemented; automatic grading is not included.

### Priority 3 - Institution adoption and future expansion

#### 8. Institution dashboard

Buyer need: a school or coaching centre can coordinate multiple teachers and classes.

- [ ] Define institution ownership, administrator permissions, invitations and teacher/class membership.

- [ ] Add institution-wide summaries of participation, practice and students needing support.

- [ ] Preserve student privacy and isolate one institution's data from another; test administrator and teacher boundaries.

- [ ] Define institution changes and historical access before adding bulk imports or exports.

- [ ] Validate demand in a small pilot before building institution billing and advanced reports.

#### 9. Other subject support

Buyer need: the platform can later support subjects beyond ICT using subject-specific learning material.

- [ ] Select the next subject only after ICT stability, content validation and a product/mentor scope decision.

- [ ] Prepare provenance-backed datasets for the subject and study level; train and connect the intended profiles.

- [ ] Audit backend subject/profile mapping, searchable topics and frontend subject selection before enabling access.

- [ ] Verify account-level filtering, relevant retrieval, quiz correctness, progress and teacher-assignment behavior.

- [ ] Confirm unsupported subjects fail clearly instead of using an unrelated profile or producing a server error.

- [ ] Preserve working ICT behavior with regression tests and actual browser checks. Dataset upload alone does not complete subject integration.

### Completion criteria and build order

- [ ] First complete the existing live retrieval/content-quality checks in Sections 22-23.

- [ ] Choose one Priority 1 enhancement and inspect its existing implementation before specifying changes.

- [ ] For each enhancement: define acceptance criteria, implement one file at a time, run affected tests and check the actual user flow.

- [ ] Record confirmed completion and test evidence here; leave unverified work unchecked.

- [ ] Evaluate a small classroom pilot before committing Priority 3 work or paid plans.

The proposed buyer roadmap extends the existing product. It does not establish complete syllabus coverage, proven learning outcomes or production readiness.

**---**

## 26. Written and Scenario-Based Topic Practice — Manual Baseline Completed; Advanced Work Pending

### Product scope

SSC/HSC remain the student's study level for selecting appropriate ICT content. Current AI generation is MCQ practice; manually authored written/practical assignments are now implemented (Section 27). Exam preparation mode supports revision-focused explanations and practice; it does not establish complete syllabus coverage or a full board-exam preparation system.

Future written practice will help students develop an idea of a topic and explain it in their own words using curated, provenance-backed material. Short-answer and scenario-based practice must be distinguished from official board questions, exam predictions and verified syllabus-specific creative-question formats.

### Phase 1 - Teacher-created written practice

- [ ] Add distinct task types for short-answer, scenario-based written practice and practical ICT assignments; reuse submission/feedback infrastructure from Section 25.7 where appropriate.

- [ ] Let teachers create a topic-linked prompt, scenario or stimulus, sub-questions, marks and an assessment rubric for their own classes.

- [x] Let students submit typed answers and code text. Handwritten photo/PDF uploads remain pending and require secure validation/private storage.

- [x] Let the teacher give manual marks and free-text improvement feedback on a saved submission.

- [ ] Save submission/review history; permit revised answers only when the teacher enables resubmission.

- [x] Enforce assignment teacher ownership, saved-recipient access and submission availability/deadline rules; 35 targeted tests passed. PostgreSQL concurrent-request behavior requires separate verification.

- [x] Keep written-task scoring separate from existing MCQ mastery.

### Phase 2 - Dataset-supported question drafts

- [ ] Generate short-answer or scenario-based question drafts from supported material for the selected ICT topic and study level.

- [ ] Require sufficient source context; do not substitute unrelated topics or invent curriculum requirements.

- [ ] Include source references when available and supported answer points/rubric drafts for teacher review.

- [ ] Let teachers review, edit and approve drafts before class assignment; source/rubric answers must not be exposed prematurely to students.

- [ ] Validate structured output separately from the existing MCQ parser so working quiz generation is preserved.

- [ ] Review factual correctness, source support, clarity and answerability; a trained dataset does not guarantee correct generated questions.

- [ ] Test both study levels, malformed responses, unsupported topics and the actual submission/feedback flow.

### Exam-format verification and presentation wording

- [ ] Verify the applicable ICT assessment format for each study level, syllabus and examination year from authoritative material before offering a board-format template. Do not assume SSC and HSC use identical formats.

- [ ] Have a qualified teacher review any syllabus-specific creative/written-question template and marking rubric.

- [ ] Describe the current app as supplementary ICT learning, revision and MCQ practice alongside textbooks and teacher guidance.

- [x] Describe manually authored written/practical tasks and teacher-marked text/code submissions as implemented. AI written/scenario generation, structured rubrics and official exam formats remain future work.

Suggested presentation wording: "The current prototype helps students understand ICT concepts, revise topics and practise MCQs from curated learning materials. Teachers can also assign manually authored written/practical tasks, receive text/code answers and provide marks and feedback. Dataset-supported written/scenario generation remains future work. It is not a claim of official board questions, exam predictions or complete examination preparation."

Automatic AI grading and official exam-paper generation are not included in this planned first implementation.

## 27. Learning Assignments — Completed and Verified, 9 October 2026

### Teacher and student flow

- [x] Teacher manually creates written/practical tasks with title, instructions, total marks, availability and deadline.

- [x] Assign to all current enrolled students or selected enrolled students; save recipients and task notifications together.

- [x] Student lists eligible tasks and submits answer text, code text, or both once before the deadline.

- [x] Preserve code indentation/newlines; display submitted code as text without executing it.

- [x] Teacher views submissions, awards marks (including zero, not above total), and saves feedback once.

- [x] Student sees saved submission, pending/reviewed status, marks and feedback after reload.

- [x] Review notification is saved; task/review notification buttons mark read and open the student Learning Assignments page.

- [x] Separate teacher `/teacher/learning-assignments` and student `/learning-assignments` pages with sidebar links and role guards.

- [x] Remove embedded written/practical controls from MCQ pages; retain existing MCQ generation/review/assignment flows.

### Implementation inventory

- Models: `learning_assignment.py`, `learning_assignment_recipient.py`, `learning_assignment_submission.py`.

- Validation: `schemas/learning_assignment_schema.py`; routes: `routes/learning_assignments.py`; imports/blueprint registration in `app.py`.

- Applied migration: `2d8f5d046695`, parent `406133132cae` (three new assignment tables).

- Tests: `tests/test_learning_assignments.py`, using existing in-memory SQLite fixtures.

- Components: `TeacherLearningAssignmentForm.vue`, `TeacherLearningAssignmentReviews.vue`, `StudentLearningAssignments.vue`.

- Views: `TeacherLearningAssignmentsView.vue`, `StudentLearningAssignmentsView.vue`.

- Integration: router, App sidebar, NotificationPanel; old TeacherQuizzesView/StudentAssignmentsView embeddings removed.

### Reported verification evidence

| Check | Result | Date |

| --- | --- | --- |

| Learning Assignments targeted suite | 35 passed | 9 October 2026 |

| Full backend suite | 1301 passed | 9 October 2026 |

| Frontend production build | Passed | 9 October 2026 |

| Teacher create → student text/code submit → teacher review → student result | Working; refresh persistence confirmed by Saif | 9 October 2026 |

| Separate pages and existing MCQ flows | Working, confirmed by Saif | 9 October 2026 |

| Learning task/review notification navigation | Working, confirmed by Saif | 9 October 2026 |

Tests and browser checks were run/reported by Saif. These are not an independent repository audit or a claim of production readiness.

### Verified backup archive checks

- Code: `/home/saifss/Desktop/ict-foundation-coach-working-20261009-182152.tar.gz`; `tar -tzf` completed successfully.

- PostgreSQL: `/home/saifss/Desktop/ict-foundation-coach-db-20261009-182206.dump`; `pg_restore --list` completed successfully.

- Database: `ict_foundation_coach`; host `localhost:5432`; application user `ict_coach_app`.

- Earlier backups retained; archive readability checks do not establish that a full restore has been rehearsed.

### Current limits and pending enhancements

- [ ] File/photo/PDF/document/spreadsheet uploads and private file storage.

- [ ] Resubmission, answer revisions and editable teacher reviews; current baseline allows one submission and one review.

- [ ] Structured rubrics, explicit topic-linked scenarios/sub-questions and dataset-supported AI written question drafts.

- [x] Individual task route exists for opening a learning task on a separate page. Notification deep-link wiring to that exact route remains to be audited.

- [ ] Unsaved-form protection across all navigation/unmount/refresh paths and mobile/accessibility review.

- [x] PostgreSQL backup restored into the Docker database and manually checked.
- [ ] Dedicated PostgreSQL concurrency/rollback audit remains pending.

- [ ] Optional calendar integration and practical-task analytics, if explicitly scoped.

Preserve the working tutor, generator prompts/profile selection and MCQ scoring while implementing any future enhancement.

---

## 28. Mentor Scope Reconciliation — Updated 12 October 2026

| Mentor suggestion | Current implementation | Limits |
| --- | --- | --- |
| One-click dataset question/answer generation | Teacher generates MCQs and answer keys, then reviews/edits before publishing and assigning. | Supported ICT datasets; factual quality still needs evaluation. |
| Class mistake and non-participation report | Questions frequently answered incorrectly, participation, not-attempted students and individual reviews. | Unsubmitted/expired attempts are distinguished; no claim of concept-level diagnosis. |
| Student weak-topic report | Latest available topic scores, attempt counts and trends; below 80% flags a topic for practice. | Unattempted topics remain separate; historical broad topic IDs can be coarse. |
| One-click weak-topic practice | Student launches supported topic practice and results update progress. | Requires supported lesson content. |
| CQ answer feedback | Written-answer AI draft feedback against a teacher reference, followed by teacher final marks/feedback. | Official board-format CQ generation, verified rubrics and automatic final grading are not implemented. |
| Textbook tutor in preferred language | Maira explanations and follow-ups in Banglish/English with saved conversations. | Source citations and systematic grounding evaluation remain pending. |
| Automatic weekly parent report | Implemented and tested after initially being deferred: Maira summarises recorded activity; Brevo sends to consenting parents. | Local worker must run; test interval was five minutes, regular schedule is weekly. |

Other subjects remain a future extension requiring appropriate datasets, profile mapping, topic/UI integration and end-to-end verification. Uploading a dataset alone does not enable a subject.

## 29. Learning Workflows and UI Improvements — Confirmed 10–12 October

### Assessment and reporting

- [x] Teacher generation navigates to a separate draft review/edit page; teacher publishes/assigns there and returns to generation after assignment.
- [x] Teacher assigned-quizzes page is separate; selected results display under the selected quiz rather than at the bottom of a long page.
- [x] Class mistake-report flow manually checked; associated tests passed.
- [x] Student weak-topic report and targeted practice manually checked; an improved result removed the tested topic from the weak list.
- [x] Separate student Start/Resume and My Attempts pages; review controls and navigation adjusted.
- [x] Learning task Open Task navigates to an individual task page with back navigation.
- [x] Teacher generated quizzes can move to History without deleting saved questions/results. Migration `13e1e4cdee7d` adds `teacher_quizzes.removed_at`.
- [x] Student assigned quizzes can move to History after at least one submitted attempt. Migration `a000b87d19c6` adds recipient `removed_at`.
- The earlier teacher-assignment removal migration `f6f332b84a0c` was rolled back and replaced by teacher-quiz history; do not reapply the abandoned design.

### Written/practical and AI support

- [x] Teacher reference-answer field; reference remains teacher-controlled assessment input.
- [x] AI can draft the reference answer in the form; teacher reviews/edits it before use.
- [x] Written-answer feedback draft contains summary, strengths, missing points and improvement suggestions; teacher decides final marks and feedback.
- [x] Reference required for AI feedback; no automatic final grade. Practical code is submitted/displayed as text, not executed.
- [x] Feedback generation rechecks concurrent teacher review and reference/answer changes before saving.
- [x] Teacher Maira access supports additional content assistance.
- Migration `0e36c23a8df0` adds assignment reference and submission AI feedback fields.

### Dashboard, Tutor and styling

- [x] Separate student `/dashboard`; login redirects students there and teachers to their dashboard. Tutor stays at `/`.
- [x] Dashboard uses actual progress, weak topics, assignments, recent feedback and calendar data with section-specific loading/error handling.
- [x] Compact motivational Banglish dashboard header; maroon Ask Maira action.
- [x] Tutor has a compact learning header, upper subject selection and more full-width conversation space; How to Practise sidebar removed.
- [x] Maroon Maira styling, consistent button hover/shadow/press transitions, blue actions, red removal/leave controls and selected purple analytics actions.
- [x] Calendar, notifications, messages, class controls, quiz/history navigation, progress and feedback UI manually checked by Saif.
- [ ] Final systematic responsive, accessibility and reduced-motion audit remains pending.

## 30. Redis and Docker Local Demo — Completed 11–12 October

### Caching

- [x] Redis caches topic-list and paginated topic-search responses for **300 seconds**.
- [x] Cache keys separate teacher visibility and student study-level scope, endpoint, search and page; permission checks run before cache access.
- [x] Topic updates/seed changes use the implemented invalidation flow; audit every future topic write path before relying on it.
- [x] Redis connection/write/read verified, with TTL observed decreasing from 245 to 208 to 187 seconds.
- [x] Cache fallback tests and dependency checks passed; caching does not replace PostgreSQL.
- [x] Docker uses Redis database 1 for topics and database 0 for rate limits.

### Runtime

- [x] Backend image: Python 3.14 slim, Gunicorn, non-root application user.
- [x] Frontend image: Node build stage, Nginx static serving and Vue history fallback.
- [x] Compose services: `db`, `redis`, `backend`, `frontend`, `weekly-reports`.
- [x] PostgreSQL 18 persistent volume; DB/Redis health checks and backend health endpoint.
- [x] Backend `.env` supplies Maira/mail settings; Compose overrides Docker DB/Redis addresses.
- [x] Local ports bind to localhost: frontend 5173, backend 5000. Stop local Flask/Vite when those ports are occupied.
- [x] Original PostgreSQL backup restored into Docker with a transaction; current migrations retained.
- [x] Docker demo copy cleaned to student IDs 1 and 19 and teacher ID 12. Teacher display name changed to **ICT Teacher**; original local DB is separate.
- [x] Verified earlier Docker backups: `ict-coach-docker-db-20261012-120121.dump` and `ict-foundation-coach-docker-ready-20261012-121727.tar.gz`.
- [x] Updated code and Docker DB backups completed after parent reports and 1491 tests. Exact new filenames were not supplied; keep the archives on the Desktop.
- [ ] Public HTTPS/domain deployment, production CORS and final secret handling audit remain pending.
- [ ] Personal calendar reminder worker is not yet shown running against Docker DB; do not assume the original local systemd timer serves the Docker copy.

### Operating commands

Run from `~/Desktop/ict-foundation-coach`:

```bash
# Start the app without starting the report worker
 docker compose --env-file .env.docker up -d --wait db redis backend frontend

# Start/recreate reports after checking mode and parent consent
 docker compose --env-file .env.docker up -d --no-deps weekly-reports

# Stop only report delivery
 docker compose --env-file .env.docker stop weekly-reports

# Inspect report logs
 docker compose --env-file .env.docker logs --tail=50 weekly-reports

# Stop containers while retaining the database volume
 docker compose --env-file .env.docker down
```

Do not use `down -v` to stop a demo: it removes persistent volumes. Code backups may include local secrets and should remain private.

## 31. Automatic Weekly Parent Progress Reports — Implemented 12 October

### Flow and permissions

- [x] Student Parent Reports settings page/sidebar link; student proposes parent email.
- [x] Parent receives a 24-hour verification link and explicitly confirms authority/consent without a student/parent login.
- [x] Hashed, expiring, single-use verification tokens; changed pending email invalidates the earlier link.
- [x] Verified parent email cannot be changed, resent or disabled through the student API; student DELETE returns 403.
- [x] Parent stops emails through a signed unsubscribe link and explicit confirmation POST; opening/scanning a link alone has no effect.
- [x] Unsubscribe preserves verified email and sets report delivery off; UI shows **Disabled by parent**.
- [ ] Parent-controlled re-enable and authorised teacher email-correction workflow are not implemented. Do not promise these controls in the demo.

### Report content and delivery

- [x] Source service collects last-seven-day ICT quiz counts/score totals, current weak-topic status, written/practical submissions, teacher-reviewed marks and due tasks without submission.
- [x] Quiz data is student/study-level scoped; assigned scores awaiting teacher review are excluded. Linked QuizAttempt records are counted once.
- [x] Weak-topic state is labelled as current latest available results, which can predate the week; no-attempt topics are not invented as weak.
- [x] Maira generates a plain-text Banglish summary and practical suggestions using supplied statistics.
- [x] Student name and parent email are not sent in the Maira report prompt. Raw chat, code, answers and teacher reference content are not part of report source data.
- [x] Full report appears in the email body; parent does not log into the student's account.
- [x] Brevo SMTP reused. Normal recipient email without a Gmail `+` alias was tested successfully.
- [x] Mentor confirmed Brevo is acceptable for the demo. GigaLogy's hidden secure-link endpoint is playground/session-oriented and was described by the mentor as unsuitable for automated weekly reporting.
- [x] Dedicated Docker worker checks every 30 seconds; delivery keys prevent duplicate processing for the same student/slot.
- [x] Demo mode delivers once per five-minute slot, still summarising seven days; email contains a test-mode notice.
- [x] Regular mode schedules Monday **09:00 Asia/Dhaka**, with a weekly delivery key.
- [x] Consent/email rechecked before SMTP sending; parent preference row locked during send.
- [x] Delivery records retain source/report and states `pending`, `ready`, `sending`, `sent`, `failed`, `uncertain`.
- `sent` means SMTP accepted, not guaranteed inbox delivery. A real inbox delivery was separately confirmed.
- SMTP uncertainty is not automatically retried; process interruption can leave a pending/sending record. Operational recovery and bounded retries remain future work.
- [ ] AI factual fidelity and wording need broader evaluation. Output-format tests do not prove every generated sentence matches source data.

### Implementation inventory

- Models: `weekly_progress_report.py`, `parent_email_verification_token.py`; parent preference fields in `user.py`.
- Services: `weekly_report_data_service.py`, `weekly_report_ai_service.py`, `parent_report_token_service.py`, `weekly_report_delivery_service.py`.
- Routes: `routes/parent_reports.py`; registered in `app.py`.
- Worker: `weekly_report_worker.py`.
- Views: `ParentReportSettingsView.vue`, `ParentReportVerifyView.vue`, `ParentReportUnsubscribeView.vue`; router and App sidebar integration.
- Migrations: `98c55f850779` parent preferences → `ccedfc10d65f` report records → `eb07af35231c` parent verification tokens; Docker head confirmed.
- Tests: `test_weekly_report_data.py` (9), `test_weekly_report_ai.py` (13), `test_parent_reports.py` (14), `test_weekly_report_delivery.py` (9): **45 passed** together.
- Configuration: `MAIRA_REPORT_PROFILE_ID` in backend `.env`; actual compatible profile ID required, not the example placeholder. `WEEKLY_REPORT_MODE=demo|weekly` in root `.env.docker`.

### Live evidence and current state

- [x] Maira generated an actual report after profile configuration was corrected.
- [x] Scheduler automatically generated and emailed a report for the tested HSC student; full body and unsubscribe link received.
- [x] Parent unsubscribe confirmation worked; settings changed to **Disabled by parent**.
- [x] Worker stopped successfully (Exited) to avoid repeated five-minute test emails.
- [x] Frontend production builds passed; Parent Reports navigation confirmed.
- [x] Full backend suite **1491 passed**, followed by code/database backup confirmation.
- [ ] Confirm `.env.docker` is saved as `WEEKLY_REPORT_MODE=weekly` before any worker restart. The five-minute mode was only a test.
- Worker and database must be available for delivery. Localhost email links work only on the demo machine; remote parents require a deployed frontend/API.

## 32. Next Work — Keep the Working Demo Stable

1. Retain the current backups and report-worker stopped state until intentionally enabling delivery.
2. Check saved weekly mode; implement parent-controlled re-enable/email correction only if needed for the next demo.
3. Rehearse student/teacher presentation flows with existing accounts and explain AI draft versus teacher-final assessment clearly.
4. Update the proposal/presentation if requested to include tested weekly parent reporting, Redis and Docker.
5. Complete final documentation, mobile/accessibility/security checks and systematic live RAG quality evaluation; CI/public deployment remain separate work.

No automatic private-book ingestion, full subject expansion, official board-exam generation, proven learning outcomes or production readiness is claimed.

