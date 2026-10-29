<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";
import { confirmAction } from "../services/confirm_dialog";
const router = useRouter();
const store = useStore();

const timezoneName = Intl.DateTimeFormat().resolvedOptions().timeZone;
const today = new Date();
const month = ref(new Date(today.getFullYear(), today.getMonth(), 1));
const selectedDate = ref(dateKey(today));
const events = ref([]);
const busy = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const editorOpen = ref(false);
const editingId = ref(null);
const editingVersion = ref(null);
const title = ref("");
const description = ref("");
const startsAt = ref("");
const endsAt = ref("");
const assistantOpen = ref(false);
const assistantMessage = ref("");
const assistantQuestion = ref("");
const assistantTarget = ref(null);
const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const pendingManualCreate = ref(null);
const pendingMairaCreate = ref(null);

async function createEventWithRetry(pending, eventBody) {
  const signature = JSON.stringify(eventBody);

  if (pending.value && pending.value.signature !== signature) {
    throw new Error(
      "The previous save is unresolved. Restore the previous details and retry, or refresh the calendar to check whether it was saved.",
    );
  }

  if (!pending.value) {
    pending.value = {
      signature,
      body: {
        ...eventBody,
        request_id: window.crypto.randomUUID(),
      },
    };
  }

  const data = await api("/api/calendar-events", "POST", pending.value.body);

  // Clear only after receiving a successful response.
  pending.value = null;
  return data;
}

async function finishMairaSave(eventBody, updating) {
  const start = parseTimestamp(eventBody.starts_at);

  resetAssistant();

  month.value = new Date(start.getFullYear(), start.getMonth(), 1);
  selectedDate.value = dateKey(start);

  successMessage.value = updating
    ? `"${eventBody.title}" updated by Maira.`
    : `"${eventBody.title}" created by Maira.`;

  await refreshAfterMutation();
}

function resetAssistant() {
  assistantOpen.value = false;
  assistantMessage.value = "";
  assistantQuestion.value = "";
  assistantTarget.value = null;
  pendingMairaCreate.value = null;
}

function openMaira(event = null) {
  if (busy.value) return;
  if (event && event.kind !== "personal") return;

  resetAssistant();
  editorOpen.value = false;

  assistantTarget.value = event
    ? {
        id: event.id,
        version: event.version,
        title: event.title,
      }
    : null;

  errorMessage.value = "";
  successMessage.value = "";
  assistantOpen.value = true;
}

function askMaira() {
  return runAction(async () => {
    const message = assistantMessage.value.trim();
    const target = assistantTarget.value;
    const updating = target !== null;

    // Retry the saved proposal directly instead of asking Maira again.
    if (!updating && pendingMairaCreate.value) {
      const body = pendingMairaCreate.value.body;
      const eventBody = {
        title: body.title,
        description: body.description,
        starts_at: body.starts_at,
        ends_at: body.ends_at,
        timezone_name: body.timezone_name,
      };

      await createEventWithRetry(pendingMairaCreate, eventBody);
      await finishMairaSave(eventBody, false);
      return;
    }

    if (!message || message.length > 1000) {
      throw new Error("Write a request containing 1–1000 characters.");
    }

    assistantQuestion.value = "";

    const requestBody = {
      message,
      timezone_name: timezoneName,
      action: updating ? "update" : "create",
    };

    if (updating) {
      requestBody.event_id = target.id;
      requestBody.version = target.version;
    }

    const data = await api(
      "/api/calendar-events/assistant",
      "POST",
      requestBody,
    );

    if (
      data.action !== requestBody.action ||
      (updating &&
        (data.event_id !== target.id || data.version !== target.version))
    ) {
      throw new Error("Maira returned an unexpected calendar response.");
    }

    const proposal = data.proposal;

    if (proposal?.status === "needs_clarification") {
      assistantQuestion.value = proposal.question;
      return;
    }

    if (proposal?.status !== "draft" || !proposal.event) {
      throw new Error("Maira returned an invalid calendar proposal.");
    }

    const draft = proposal.event;
    const start = parseTimestamp(draft.starts_at);
    const end = parseTimestamp(draft.ends_at);

    if (
      !Number.isFinite(start.getTime()) ||
      !Number.isFinite(end.getTime()) ||
      end <= start ||
      draft.timezone_name !== timezoneName
    ) {
      throw new Error("Maira returned invalid event times or timezone.");
    }

    const eventBody = {
      title: draft.title,
      description: draft.description,
      starts_at: draft.starts_at,
      ends_at: draft.ends_at,
      timezone_name: draft.timezone_name,
    };

    if (updating) {
      await api(`/api/calendar-events/${target.id}`, "PUT", {
        ...eventBody,
        version: target.version,
      });
    } else {
      await createEventWithRetry(pendingMairaCreate, eventBody);
    }

    await finishMairaSave(eventBody, updating);
  });
}
function pad(value) {
  return String(value).padStart(2, "0");
}

function dateKey(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function localInput(date) {
  return `${dateKey(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function parseTimestamp(value) {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
    ? value
    : `${value}Z`;

  return new Date(normalized);
}

function formatTime(value) {
  return parseTimestamp(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

const monthLabel = computed(() =>
  month.value.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  }),
);

const visibleStart = computed(() => {
  const start = new Date(month.value);
  start.setDate(1 - start.getDay());
  return start;
});

const visibleEnd = computed(() => {
  const end = new Date(visibleStart.value);
  end.setDate(end.getDate() + 42);
  return end;
});

function eventsForDay(date) {
  const start = new Date(date);
  start.setHours(0, 0, 0, 0);

  const end = new Date(start);
  end.setDate(end.getDate() + 1);

  return events.value.filter(
    (event) =>
      parseTimestamp(event.starts_at) < end &&
      parseTimestamp(event.ends_at) > start,
  );
}

const days = computed(() =>
  Array.from({ length: 42 }, (_, index) => {
    const date = new Date(visibleStart.value);
    date.setDate(date.getDate() + index);

    return {
      key: dateKey(date),
      number: date.getDate(),
      inMonth: date.getMonth() === month.value.getMonth(),
      today: dateKey(date) === dateKey(today),
      events: eventsForDay(date),
    };
  }),
);

const selectedEvents = computed(() => {
  const [year, monthNumber, day] = selectedDate.value.split("-").map(Number);
  return eventsForDay(new Date(year, monthNumber - 1, day));
});

function firstMessage(value) {
  if (typeof value === "string") return value;

  if (value && typeof value === "object") {
    for (const child of Object.values(value)) {
      const message = firstMessage(child);
      if (message) return message;
    }
  }

  return "";
}

async function api(path, method = "GET", body) {
  const response = await fetch(`http://127.0.0.1:5000${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${store.state.auth.accessToken}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");
    await router.replace("/login");
    throw new Error("Your session expired. Please log in again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Could not read the server response.");
  }

  if (!response.ok) {
    throw new Error(
      firstMessage(data.messages) || data.error || "Calendar request failed.",
    );
  }

  return data;
}

async function fetchCalendarPages(path, responseKey) {
  const collected = [];

  for (let page = 1; page <= 10000; page += 1) {
    const query = new URLSearchParams({
      starts_at: visibleStart.value.toISOString(),
      ends_at: visibleEnd.value.toISOString(),
      page: String(page),
    });

    const data = await api(`${path}?${query}`);
    collected.push(...data[responseKey]);

    if (!data.pagination.has_more) {
      return collected;
    }
  }

  throw new Error("Too many calendar entries to display.");
}

async function fetchEvents() {
  const personalEvents = await fetchCalendarPages(
    "/api/calendar-events",
    "events",
  );

  const assignments = await fetchCalendarPages(
    "/api/calendar-events/assignments",
    "assignments",
  );

  const classExams = await fetchCalendarPages("/api/class-exams", "exams");

  events.value = [
    ...personalEvents.map((event) => ({
      ...event,
      kind: "personal",
      calendarKey: `personal-${event.id}`,
    })),
    ...assignments.map((assignment) => ({
      ...assignment,
      calendarKey: `assignment-${assignment.id}`,
    })),
    ...classExams.map((exam) => ({
      ...exam,
      kind: "class_exam",
      calendarKey: `exam-${exam.id}`,
    })),
  ].sort(
    (first, second) =>
      parseTimestamp(first.starts_at).getTime() -
      parseTimestamp(second.starts_at).getTime(),
  );
}

function openQuizPage() {
  if (busy.value) return;

  router.push({
    name:
      store.state.auth.currentUser?.role === "teacher"
        ? "teacher-quizzes"
        : "student-assignments",
  });
}

async function runAction(action) {
  if (busy.value) return;

  busy.value = true;
  errorMessage.value = "";
  successMessage.value = "";

  try {
    await action();
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Something went wrong.";
  } finally {
    busy.value = false;
  }
}

function refreshEvents() {
  return runAction(fetchEvents);
}

function changeMonth(offset) {
  if (busy.value) return;

  month.value = new Date(
    month.value.getFullYear(),
    month.value.getMonth() + offset,
    1,
  );
  selectedDate.value = dateKey(month.value);
  events.value = [];
  refreshEvents();
}

function goToToday() {
  if (busy.value) return;

  const current = new Date();
  month.value = new Date(current.getFullYear(), current.getMonth(), 1);
  selectedDate.value = dateKey(current);
  events.value = [];
  refreshEvents();
}
function openCreate() {
  if (busy.value) return;
  resetAssistant();

  pendingManualCreate.value = null;
  editingId.value = null;
  editingVersion.value = null;
  title.value = "";
  description.value = "";
  startsAt.value = `${selectedDate.value}T20:00`;
  endsAt.value = `${selectedDate.value}T21:00`;
  errorMessage.value = "";
  successMessage.value = "";
  editorOpen.value = true;
}

function openEdit(event) {
  if (busy.value || event.kind !== "personal") return;
  resetAssistant();

  editingId.value = event.id;
  editingVersion.value = event.version;
  title.value = event.title;
  description.value = event.description;
  startsAt.value = localInput(parseTimestamp(event.starts_at));
  endsAt.value = localInput(parseTimestamp(event.ends_at));
  errorMessage.value = "";
  successMessage.value = "";
  editorOpen.value = true;
}

async function refreshAfterMutation() {
  try {
    await fetchEvents();
  } catch {
    errorMessage.value =
      "Your change was saved, but the calendar refresh failed. Click Refresh.";
  }
}

function saveEvent() {
  return runAction(async () => {
    const start = new Date(startsAt.value);
    const end = new Date(endsAt.value);

    if (
      !startsAt.value ||
      !endsAt.value ||
      !Number.isFinite(start.getTime()) ||
      !Number.isFinite(end.getTime())
    ) {
      throw new Error("Enter valid start and end times.");
    }

    if (end <= start) {
      throw new Error("End time must be after start time.");
    }

    const eventTitle = title.value.trim();

    if (!eventTitle || eventTitle.length > 150) {
      throw new Error("Title must contain 1–150 characters.");
    }

    const body = {
      title: eventTitle,
      description: description.value.trim(),
      starts_at: start.toISOString(),
      ends_at: end.toISOString(),
      timezone_name: timezoneName,
    };

    const updating = editingId.value !== null;

    if (updating) {
      body.version = editingVersion.value;
    }

    if (updating) {
      await api(`/api/calendar-events/${editingId.value}`, "PUT", body);
    } else {
      await createEventWithRetry(pendingManualCreate, body);
    }

    // Close after successful save, even if the list refresh later fails.
    editorOpen.value = false;
    successMessage.value = updating ? "Event updated." : "Event created.";
    await refreshAfterMutation();
  });
}

function deleteEvent(event) {
  if (busy.value || event.kind !== "personal") return;

  const eventId = event.id;
  const eventVersion = event.version;
  const token = store.state.auth.accessToken;

  return runAction(async () => {
    const accepted = await confirmAction({
      title: "Delete this event?",
      message:
        `Delete "${event.title}" from your calendar?\n\n` +
        "This action cannot be undone.",
      confirmText: "Delete event",
      cancelText: "Cancel",
      variant: "danger",
    });

    if (!accepted || store.state.auth.accessToken !== token) return;

    await api(`/api/calendar-events/${eventId}`, "DELETE", {
      version: eventVersion,
    });

    if (editingId.value === eventId) {
      editorOpen.value = false;
    }

    successMessage.value = "Event deleted.";
    await refreshAfterMutation();
  });
}

onMounted(refreshEvents);
</script>

<template>
  <section class="calendar-page" :aria-busy="busy">
    <header class="heading-row">
      <div>
        <p class="eyebrow">MY CALENDAR</p>
        <h1>Plan your activities</h1>
        <p class="description">
          Your personal events are private. All times use {{ timezoneName }}.
        </p>
      </div>

      <button type="button" :disabled="busy" @click="refreshEvents">
        {{ busy ? "Please wait..." : "Refresh" }}
      </button>
    </header>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>

    <p v-if="successMessage" class="success" role="status">
      {{ successMessage }}
    </p>

    <section class="panel">
      <div class="heading-row">
        <h2>{{ monthLabel }}</h2>

        <div class="actions">
          <button
            type="button"
            :disabled="busy"
            aria-label="Previous month"
            @click="changeMonth(-1)"
          >
            Previous
          </button>

          <button type="button" :disabled="busy" @click="goToToday">
            Today
          </button>

          <button
            type="button"
            :disabled="busy"
            aria-label="Next month"
            @click="changeMonth(1)"
          >
            Next
          </button>
        </div>
      </div>

      <div class="calendar-grid">
        <span v-for="day in weekdays" :key="day" class="weekday">
          {{ day }}
        </span>

        <button
          v-for="day in days"
          :key="day.key"
          type="button"
          class="day"
          :class="{
            muted: !day.inMonth,
            selected: selectedDate === day.key,
            today: day.today,
          }"
          :disabled="busy"
          :aria-pressed="selectedDate === day.key"
          :aria-label="`${day.key}: ${day.events.length} events`"
          @click="selectedDate = day.key"
        >
          <strong>{{ day.number }}</strong>

          <span v-if="day.events.length" class="event-count">
            {{ day.events.length }}
            <span class="count-label">events</span>
          </span>
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="heading-row">
        <h2>Events · {{ selectedDate }}</h2>

        <div class="actions">
          <button
            type="button"
            class="primary"
            :disabled="busy"
            @click="openCreate"
          >
            Add manually
          </button>

          <button type="button" :disabled="busy" @click="openMaira()">
            Ask Maira
          </button>
        </div>
      </div>

      <p v-if="!busy && selectedEvents.length === 0" class="description">
        No events, assigned quizzes or class exams on this date.
      </p>

      <div class="event-list">
        <article
          v-for="event in selectedEvents"
          :key="event.calendarKey"
          class="event-card"
          :class="{ 'assignment-card': event.kind !== 'personal' }"
        >
          <div class="heading-row">
            <h3>{{ event.title }}</h3>

            <span class="event-kind">
              {{
                event.kind === "quiz_assignment"
                  ? "Assigned quiz"
                  : event.kind === "class_exam"
                    ? "Class exam"
                    : "Personal"
              }}
            </span>
          </div>

          <template v-if="event.kind === 'quiz_assignment'">
            <p class="description">
              {{ event.classroom_name }} · {{ event.question_count }} questions
            </p>

            <p class="description">
              Available from: {{ formatTime(event.starts_at) }}
              <br />
              Deadline: {{ formatTime(event.ends_at) }}
              <br />
              Review from: {{ formatTime(event.review_at) }}
            </p>

            <p class="description">
              Attempt time limit: {{ event.time_limit_minutes }} minutes ·
              Allowed attempts: {{ event.max_attempts }}
            </p>

            <p class="description">
              This calendar entry shows the official quiz availability window.
            </p>

            <button type="button" :disabled="busy" @click="openQuizPage">
              {{
                store.state.auth.currentUser?.role === "teacher"
                  ? "Open teacher quizzes"
                  : "Open assigned quizzes"
              }}
            </button>
          </template>
          <template v-else-if="event.kind === 'class_exam'">
            <p class="description">
              {{ event.classroom_name }} · Total marks:
              {{ event.total_marks }}
            </p>

            <p class="description">
              Starts: {{ formatTime(event.starts_at) }}
              <br />
              Ends: {{ formatTime(event.ends_at) }}
            </p>

            <p v-if="event.description" class="event-description">
              {{ event.description }}
            </p>

            <p class="description">
              {{
                event.results_published_at
                  ? "Results published."
                  : "Results have not been published yet."
              }}
            </p>

            <p class="description">
              Official class exam schedule. The exam takes place outside this
              app.
            </p>
          </template>

          <template v-else>
            <p class="description">
              {{ formatTime(event.starts_at) }} —
              {{ formatTime(event.ends_at) }}
            </p>

            <p v-if="event.description" class="event-description">
              {{ event.description }}
            </p>

            <div class="actions">
              <button type="button" :disabled="busy" @click="openEdit(event)">
                Edit manually
              </button>

              <button type="button" :disabled="busy" @click="openMaira(event)">
                Update with Maira
              </button>

              <button
                type="button"
                class="delete"
                :disabled="busy"
                @click="deleteEvent(event)"
              >
                Delete
              </button>
            </div>
          </template>
        </article>
      </div>
    </section>

    <section v-if="assistantOpen" class="panel">
      <div class="heading-row">
        <h2>
          {{ assistantTarget ? "Update with Maira" : "Create with Maira" }}
        </h2>

        <button type="button" :disabled="busy" @click="resetAssistant">
          Cancel
        </button>
      </div>

      <p v-if="assistantTarget" class="description">
        Updating: <strong>{{ assistantTarget.title }}</strong>
      </p>

      <p class="description">
        {{
          assistantTarget
            ? "Ei event-e ki change korte chao bolo."
            : "Activity, date, start time ar end time bolo."
        }}
        Complete request hole Maira automatically save korbe. Times use
        {{ timezoneName }}.
      </p>

      <form @submit.prevent="askMaira">
        <fieldset :disabled="busy">
          <label>
            Your request
            <textarea
              v-model="assistantMessage"
              required
              :readonly="pendingMairaCreate !== null"
              maxlength="1000"
              rows="3"
              :placeholder="
                assistantTarget
                  ? 'Ei event kalke rat 9ta theke 10tay move koro'
                  : 'Kalke rat 8ta theke 9ta Math practice-er event banao'
              "
            ></textarea>
          </label>

          <button
            type="submit"
            class="primary assistant-button"
            :disabled="busy || !assistantMessage.trim()"
          >
            {{
              busy
                ? "Please wait..."
                : pendingMairaCreate
                  ? "Retry save"
                  : assistantTarget
                    ? "Update with Maira"
                    : "Create with Maira"
            }}
          </button>
        </fieldset>
      </form>

      <div v-if="assistantQuestion" role="status">
        <p class="assistant-question">{{ assistantQuestion }}</p>

        <p class="description">
          Tomar request-e missing information add kore abar submit koro.
        </p>
      </div>

      <p v-if="errorMessage" class="error" role="alert">
        {{ errorMessage }}
      </p>
    </section>

    <section v-if="editorOpen" class="panel">
      <div class="heading-row">
        <h2>{{ editingId ? "Edit manually" : "Add manually" }}</h2>

        <button type="button" :disabled="busy" @click="editorOpen = false">
          Cancel
        </button>
      </div>

      <p class="description">
        Enter times in {{ timezoneName }}. If an event changed elsewhere,
        refresh the calendar and reopen Edit before saving again.
      </p>

      <p v-if="errorMessage" class="error" role="alert">
        {{ errorMessage }}
      </p>

      <form @submit.prevent="saveEvent">
        <fieldset :disabled="busy" class="form-grid">
          <label class="wide">
            Title
            <input v-model="title" required maxlength="150" />
          </label>

          <label class="wide">
            Description (optional)
            <textarea
              v-model="description"
              maxlength="2000"
              rows="3"
            ></textarea>
          </label>

          <label>
            Starts at
            <input v-model="startsAt" type="datetime-local" required />
          </label>

          <label>
            Ends at
            <input v-model="endsAt" type="datetime-local" required />
          </label>

          <button type="submit" class="primary wide">
            {{ busy ? "Saving..." : "Save event" }}
          </button>
        </fieldset>
      </form>
    </section>
  </section>
</template>

<style scoped>
.calendar-page {
  display: grid;
  gap: 1.25rem;
  min-width: 0;
  color: var(--text-primary);
}

h1,
h2,
h3,
p {
  overflow-wrap: anywhere;
}

h1,
h2,
h3 {
  margin: 0;
}

h1 {
  font-size: clamp(1.6rem, 4vw, 2.3rem);
}

h2 {
  font-size: 1.2rem;
}

h3 {
  font-size: 1rem;
}

.eyebrow {
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.description {
  color: var(--text-secondary);
  line-height: 1.6;
}

.heading-row,
.actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.heading-row {
  justify-content: space-between;
}

.panel,
.event-card {
  padding: 1.25rem;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
  min-width: 0;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0.4rem;
  margin-top: 1rem;
}

.weekday {
  text-align: center;
  padding: 0.5rem 0;
  color: var(--text-secondary);
  font-size: 0.8rem;
}

.day {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  min-height: 80px;
  padding: 0.65rem 0.2rem;
}

.day.muted {
  color: var(--text-secondary);
}

.day.selected {
  border-color: var(--accent-color);
  background: var(--nav-hover);
}

.day.today strong {
  text-decoration: underline;
  text-underline-offset: 0.3rem;
}

.event-count {
  font-size: 0.7rem;
  color: var(--accent-color);
}

.event-list {
  display: grid;
  gap: 1rem;
  margin-top: 1rem;
}

.event-description {
  white-space: pre-wrap;
  line-height: 1.6;
}

fieldset {
  border: 0;
  padding: 0;
  margin: 1rem 0 0;
  min-width: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.wide {
  grid-column: 1 / -1;
}

label {
  display: grid;
  gap: 0.5rem;
  min-width: 0;
  font-weight: 600;
}

input,
textarea,
button {
  box-sizing: border-box;
  font: inherit;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
}

input,
textarea {
  width: 100%;
  min-width: 0;
  padding: 0.8rem;
  color: var(--text-primary);
  background: var(--page-background);
}

textarea {
  resize: vertical;
}

button {
  padding: 0.7rem 1rem;
  color: var(--accent-color);
  background: var(--surface-color);
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

button:hover:not(:disabled) {
  background: var(--nav-hover);
  transform: translateY(-2px);
}

.primary {
  color: #fff;
  background: var(--accent-color);
}

.primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.delete,
.error {
  color: #dc2626;
}

.success {
  color: var(--accent-color);
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

@media (max-width: 540px) {
  .panel {
    padding: 0.8rem;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .day {
    min-height: 64px;
    font-size: 0.8rem;
  }

  .count-label {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
.assignment-card {
  border-left: 4px solid var(--accent-color);
}

.event-kind {
  padding: 0.35rem 0.65rem;
  border-radius: 0.5rem;
  color: var(--accent-color);
  background: var(--nav-hover);
  font-size: 0.8rem;
  font-weight: 700;
}
.assistant-box {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  background: var(--page-background);
}

.assistant-button {
  margin-top: 0.75rem;
}

.assistant-question {
  color: var(--accent-color);
  font-weight: 600;
  line-height: 1.6;
}
.calendar-page button:not(.day) {
  border: 1px solid transparent;
  border-radius: 0.65rem;
  padding: 0.75rem 1rem;
  background: #2450db;
  color: #fff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.calendar-page button:not(.day):hover:not(:disabled) {
  background: #1d3fb8;
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.calendar-page button:not(.day):active:not(:disabled) {
  transform: scale(0.98);
}

.calendar-page button:not(.day):focus-visible {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}

.calendar-page button:not(.day):disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.calendar-page button.delete {
  border-color: #dc2626;
  background: transparent;
  color: #dc2626;
}

.calendar-page button.delete:hover:not(:disabled) {
  background: rgb(220 38 38 / 10%);
  color: #dc2626;
  box-shadow: 0 0.6rem 1rem rgb(220 38 38 / 20%);
  transform: translateY(-2px);
}

.calendar-page button.delete:focus-visible {
  outline-color: #dc2626;
}
.calendar-page button.day {
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.calendar-page button.day:hover:not(:disabled) {
  border-color: #2450db;
  background: var(--nav-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.calendar-page button.day:active:not(:disabled) {
  transform: scale(0.98);
}

.calendar-page button.day.selected {
  border-color: #2450db;
  background: var(--nav-hover);
}
</style>
