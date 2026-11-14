import { createRoot } from "react-dom/client";
import {
  type Dispatch,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ArrowLeft,
  Bot,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Clock3,
  Compass,
  ExternalLink,
  ImageOff,
  LogIn,
  LogOut,
  LoaderCircle,
  MapPin,
  MessageCircle,
  Network,
  Plus,
  RotateCcw,
  Save,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserPlus,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";
import "./index.css";
import { text, type Language, type TextMessageKey } from "./i18n";

type Source = { title: string; url: string };
type Visual = {
  image_url: string;
  image_page_url: string;
  image_alt: string;
  image_credit: string;
  image_license: string;
  image_data_base64?: string;
  image_media_type?: string;
};
type Entry = {
  id: string;
  day_index: number;
  start_time: string;
  end_time: string;
  notes?: string;
  place: {
    name: string;
    description: string;
    visit_minutes_estimate: number;
    travel_minutes_estimate: number;
    opening_hours?: string;
    opening_hours_verified: boolean;
    source_references: Source[];
  };
};
type Plan = {
  destination: string;
  start_date: string;
  day_count: number;
  revision: number;
  summary: string;
  entries: Entry[];
};
type TurnResponse = {
  status: string;
  message: string;
  validation_issues: { code: string; message: string }[];
};
type ChatMessage = {
  id: string;
  role: "user" | "agent";
  content: string;
  issues?: string[];
  status?: string;
  source_references?: Source[];
};
type ApiState = {
  language: Language;
  plan: Plan | null;
  pending: boolean;
  response: TurnResponse | null;
  visuals_by_entry?: Record<string, Visual>;
  conversation: {
    role: "user" | "assistant";
    content: string;
    source_references?: Source[];
  }[];
};
type SavedTourSummary = {
  id: string;
  title: string;
  destination: string;
  start_date: string;
  day_count: number;
  revision: number;
  saved_at: string;
};
type SavedTour = SavedTourSummary & {
  plan: Plan;
  visuals_by_entry?: Record<string, Visual>;
};
type SavedTourPage = {
  items: SavedTourSummary[];
  has_more: boolean;
  next_cursor: string | null;
};
type AuthState = {
  authenticated: boolean;
  email?: string;
  csrf_token?: string;
  is_admin?: boolean;
  access_status?: "active" | "blocked" | "pending";
};
type AdminUser = {
  id: string;
  email: string | null;
  created_at: string;
  access_status: "active" | "blocked" | "pending";
  is_admin: boolean;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | string | null;
};
type AdminUsersPage = {
  items: AdminUser[];
  usage_available: boolean;
  has_more: boolean;
  next_cursor: string | null;
};
type AdminUsageModel = {
  provider: string;
  model: string;
  role: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | string | null;
  unpriced_calls: number;
};
type AdminUsage = {
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | string | null;
  unpriced_calls: number;
  by_model: AdminUsageModel[];
};
type ClaimResult = {
  claimed_count: number;
  already_claimed_count: number;
  conflicts: unknown[];
};
type View = "itinerary" | "graph" | "saved" | "admin";
type LocalizedMessage = TextMessageKey | "";
type FormErrorField = "destination" | "startDate" | "days" | "chat";
type FormErrors = Partial<Record<FormErrorField, TextMessageKey>>;
const savedToursPageSize = 50;
const adminUsersPageSize = 50;
const dateLocale = (language: Language) =>
  language === "vi" ? "vi-VN" : "en-US";

function formatDateOnly(value: string, language: Language): string {
  const date = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(dateLocale(language), {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(date);
}

const today = (() => {
  const date = new Date();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
})();
const currentMonthStart = `${today.slice(0, 7)}-01`;

type DatePickerLabels = {
  startDate: string;
  previousMonth: string;
  nextMonth: string;
  closeCalendar: string;
};

function isoDateToUtc(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day, 12));
}

function utcDateToIso(value: Date): string {
  const year = value.getUTCFullYear().toString().padStart(4, "0");
  const month = (value.getUTCMonth() + 1).toString().padStart(2, "0");
  const day = value.getUTCDate().toString().padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shiftIsoMonth(value: string, months: number): string {
  const current = isoDateToUtc(value);
  const targetMonth = new Date(
    Date.UTC(current.getUTCFullYear(), current.getUTCMonth() + months, 1, 12),
  );
  const lastDay = new Date(
    Date.UTC(targetMonth.getUTCFullYear(), targetMonth.getUTCMonth() + 1, 0, 12),
  ).getUTCDate();
  targetMonth.setUTCDate(Math.min(current.getUTCDate(), lastDay));
  return utcDateToIso(targetMonth);
}

function StartDatePicker({
  value,
  language,
  labels,
  disabled,
  invalid,
  describedBy,
  onChange,
}: {
  value: string;
  language: Language;
  labels: DatePickerLabels;
  disabled: boolean;
  invalid: boolean;
  describedBy?: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState(value.slice(0, 7));
  const [focusedDate, setFocusedDate] = useState(value);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dayButtonRefs = useRef(new Map<string, HTMLButtonElement>());
  const locale = dateLocale(language);
  const weekStartsOn = language === "vi" ? 1 : 0;
  const monthDate = isoDateToUtc(`${viewMonth}-01`);
  const monthLabel = new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(monthDate);
  const weekdayFormat = new Intl.DateTimeFormat(locale, {
    weekday: "short",
    timeZone: "UTC",
  });
  const weekdayLongFormat = new Intl.DateTimeFormat(locale, {
    weekday: "long",
    timeZone: "UTC",
  });
  const fullDateFormat = new Intl.DateTimeFormat(locale, {
    dateStyle: "full",
    timeZone: "UTC",
  });
  const weekdayHeaders = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(Date.UTC(2021, 7, 1 + weekStartsOn + index, 12));
    return {
      short: weekdayFormat.format(date),
      long: weekdayLongFormat.format(date),
    };
  });
  const firstWeekday = monthDate.getUTCDay();
  const leadingDays = (firstWeekday - weekStartsOn + 7) % 7;
  const daysInMonth = new Date(
    Date.UTC(monthDate.getUTCFullYear(), monthDate.getUTCMonth() + 1, 0, 12),
  ).getUTCDate();
  const cellCount = Math.ceil((leadingDays + daysInMonth) / 7) * 7;
  const gridStart = new Date(
    Date.UTC(
      monthDate.getUTCFullYear(),
      monthDate.getUTCMonth(),
      1 - leadingDays,
      12,
    ),
  );
  const calendarDates = Array.from({ length: cellCount }, (_, index) => {
    const date = new Date(gridStart);
    date.setUTCDate(gridStart.getUTCDate() + index);
    return date;
  });

  useEffect(() => {
    if (open) dayButtonRefs.current.get(focusedDate)?.focus();
  }, [focusedDate, open]);

  useEffect(() => {
    if (!open) return;
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const focusDate = (date: Date) => {
    const next = utcDateToIso(date);
    setFocusedDate(next);
    setViewMonth(next.slice(0, 7));
  };

  const openCalendar = () => {
    setFocusedDate(value);
    setViewMonth(value.slice(0, 7));
    setOpen(true);
  };

  const closeCalendar = () => {
    setOpen(false);
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  };

  const changeMonth = (amount: number) => {
    const next = shiftIsoMonth(`${viewMonth}-01`, amount);
    setViewMonth(next.slice(0, 7));
    setFocusedDate(next);
  };

  const handleDayKeyDown = (
    event: ReactKeyboardEvent<HTMLButtonElement>,
    date: Date,
  ) => {
    const dayOffsets: Record<string, number> = {
      ArrowLeft: -1,
      ArrowRight: 1,
      ArrowUp: -7,
      ArrowDown: 7,
    };
    if (event.key in dayOffsets) {
      event.preventDefault();
      const next = new Date(date);
      next.setUTCDate(next.getUTCDate() + dayOffsets[event.key]);
      focusDate(next);
      return;
    }
    if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const weekdayIndex = (date.getUTCDay() - weekStartsOn + 7) % 7;
      const next = new Date(date);
      next.setUTCDate(
        next.getUTCDate() + (event.key === "Home" ? -weekdayIndex : 6 - weekdayIndex),
      );
      focusDate(next);
      return;
    }
    if (event.key === "PageUp" || event.key === "PageDown") {
      event.preventDefault();
      const months = (event.key === "PageUp" ? -1 : 1) * (event.shiftKey ? 12 : 1);
      const next = isoDateToUtc(shiftIsoMonth(utcDateToIso(date), months));
      focusDate(next);
    }
  };

  return (
    <div className="relative mt-2" ref={rootRef}>
      <button
        type="button"
        id="start-date"
        ref={triggerRef}
        aria-labelledby="start-date-label start-date-value"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? "start-date-calendar" : undefined}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        disabled={disabled}
        onClick={() => (open ? closeCalendar() : openCalendar())}
        className="flex min-h-12 w-full items-center justify-between rounded-xl border border-slate-300 bg-white px-3 text-left font-normal focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span id="start-date-value">{formatDateOnly(value, language)}</span>
        <CalendarDays size={18} aria-hidden="true" />
      </button>
      {open && (
        <div
          id="start-date-calendar"
          role="dialog"
          aria-label={labels.startDate}
          className="absolute left-0 top-full z-50 mt-2 w-[min(21rem,calc(100vw-2rem))] rounded-2xl border border-blue-100 bg-white p-3 shadow-xl"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <button
              type="button"
              aria-label={labels.previousMonth}
              onClick={() => changeMonth(-1)}
              className="inline-flex size-10 items-center justify-center rounded-lg text-slate-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
            >
              <ChevronLeft size={18} aria-hidden="true" />
            </button>
            <h3
              id="start-date-calendar-title"
              className="text-center font-semibold text-slate-900"
            >
              {monthLabel}
            </h3>
            <button
              type="button"
              aria-label={labels.nextMonth}
              onClick={() => changeMonth(1)}
              className="inline-flex size-10 items-center justify-center rounded-lg text-slate-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
            >
              <ChevronRight size={18} aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-label={labels.closeCalendar}
              onClick={closeCalendar}
              className="inline-flex size-10 items-center justify-center rounded-lg text-slate-600 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>
          <table
            aria-labelledby="start-date-calendar-title"
            className="w-full table-fixed text-center text-sm"
          >
            <thead>
              <tr>
                {weekdayHeaders.map((weekday, index) => (
                  <th className="h-9 font-medium text-slate-500" key={index} scope="col">
                    <abbr className="no-underline" title={weekday.long}>
                      {weekday.short}
                    </abbr>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: cellCount / 7 }, (_, row) => (
                <tr key={row}>
                  {calendarDates.slice(row * 7, row * 7 + 7).map((date) => {
                    const isoDate = utcDateToIso(date);
                    const isCurrentMonth = date.getUTCMonth() === monthDate.getUTCMonth();
                    const isSelected = isoDate === value;
                    const isToday = isoDate === today;
                    return (
                      <td className="p-0.5" key={isoDate}>
                        <button
                          type="button"
                          ref={(element) => {
                            if (element) dayButtonRefs.current.set(isoDate, element);
                            else dayButtonRefs.current.delete(isoDate);
                          }}
                          tabIndex={isoDate === focusedDate ? 0 : -1}
                          aria-label={fullDateFormat.format(date)}
                          aria-pressed={isSelected}
                          aria-current={isToday ? "date" : undefined}
                          onClick={() => {
                            onChange(isoDate);
                            closeCalendar();
                          }}
                          onKeyDown={(event) => handleDayKeyDown(event, date)}
                          className={`min-h-10 w-full rounded-lg font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 ${isSelected ? "bg-primary text-white" : isToday ? "border border-primary text-primary" : "text-slate-800 hover:bg-blue-50"} ${isCurrentMonth ? "" : "text-slate-400"}`}
                        >
                          {date.getUTCDate()}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new ApiError(body?.detail || response.statusText, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

function apiErrorMessageKey(
  error: unknown,
  fallback: TextMessageKey,
): TextMessageKey {
  if (!(error instanceof ApiError)) return fallback;
  if (error.status === 401) return "sessionExpired";
  if (error.status === 409) return "turnPending";
  if (error.status === 429) return "turnRateLimited";
  if (error.status === 503) return "serviceUnavailable";
  return fallback;
}
function FieldError({ message }: { message?: string }) {
  return message ? (
    <p className="mt-1 text-sm font-medium text-red-700">{message}</p>
  ) : null;
}
function Photo({ visual, placeName, language }: { visual?: Visual; placeName: string; language: Language }) {
  const labels = text(language);
  if (!visual)
    return (
      <div className="flex aspect-[16/9] items-center justify-center rounded-2xl bg-blue-50 px-4 text-center text-sm text-slate-500">
        <ImageOff className="mr-2 size-4" />
        {labels.photoUnavailable} {placeName}.
      </div>
    );
  return (
    <figure>
      <a
        href={visual.image_page_url}
        target="_blank"
        rel="noreferrer"
        className="block overflow-hidden rounded-2xl focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300"
      >
        <img
          src={
            visual.image_data_base64 && visual.image_media_type
              ? `data:${visual.image_media_type};base64,${visual.image_data_base64}`
              : visual.image_url
          }
          alt={visual.image_alt}
          className="aspect-[16/9] w-full object-cover"
          loading="lazy"
        />
      </a>
      <figcaption className="mt-2 text-xs leading-5 text-slate-500">
        {labels.photoCredit}: {visual.image_credit} · {visual.image_license} ·{" "}
        <a
          href={visual.image_page_url}
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-accent hover:underline"
        >
          {labels.photoSource}
        </a>
      </figcaption>
    </figure>
  );
}
function TurnStatus({
  response,
  className = "mt-6",
}: {
  response: TurnResponse | null;
  className?: string;
}) {
  if (!response) return null;
  const committed = response.status === "committed";
  return (
    <section
      className={`rise rounded-2xl border p-4 ${className} ${committed ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex gap-3">
        <CheckCircle2
          className={
            committed ? "shrink-0 text-emerald-600" : "shrink-0 text-amber-600"
          }
        />
        <div>
          <p className="font-semibold">{response.message}</p>
          {response.validation_issues.map((issue) => (
            <p className="mt-1 text-sm text-slate-700" key={issue.code}>
              {issue.message}
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}
function PlanView({
  plan,
  visuals,
  loading,
  language,
  statusLabel,
  titleId = "itinerary-title",
}: {
  plan: Plan;
  visuals: Record<string, Visual>;
  loading: boolean;
  language: Language;
  statusLabel?: string;
  titleId?: string;
}) {
  const labels = text(language);
  const days = Array.from({ length: plan.day_count }, (_, index) => index + 1);
  return (
    <section aria-labelledby={titleId} className="rise mt-8">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-primary">
            {statusLabel ?? labels.verified}
          </p>
          <h2 id={titleId} className="font-heading text-2xl font-bold">
            {plan.destination}{" "}
            <span className="text-slate-500">· v{plan.revision}</span>
          </h2>
        </div>
        <p className="text-sm text-slate-600">
          <time dateTime={plan.start_date}>
            {formatDateOnly(plan.start_date, language)}
          </time>
          {" · "}
          {plan.day_count} {labels.dayUnit}
        </p>
      </div>
      {plan.summary && (
        <p className="mb-5 max-w-3xl text-slate-700">{plan.summary}</p>
      )}
      {loading && (
        <p
          className="mb-4 inline-flex items-center gap-2 text-sm text-slate-600"
          role="status"
        >
          <LoaderCircle className="size-4 animate-spin" />
          {labels.findingPhotos}
        </p>
      )}
      <div className="grid gap-5 xl:grid-cols-2">
        {days.map((day) => {
          const entries = plan.entries
            .filter((entry) => entry.day_index === day)
            .sort((a, b) =>
              a.start_time.localeCompare(b.start_time) ||
              a.end_time.localeCompare(b.end_time) ||
              a.id.localeCompare(b.id),
            );
          return (
            <article
              className="rounded-3xl border border-blue-100 bg-white p-5 shadow-sm"
              key={day}
            >
              <h3 className="font-heading text-lg font-bold">{labels.day} {day}</h3>
              <div className="mt-4 space-y-6">
                {entries.length ? (
                  entries.map((entry, index) => (
                    <article
                      className="border-l-2 border-blue-500 pl-4"
                      key={entry.id}
                    >
                      <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-blue-700">
                        <Clock3 size={16} />
                        {entry.start_time.slice(0, 5)}–
                        {entry.end_time.slice(0, 5)}{" "}
                        <span className="text-slate-500">·</span> {labels.stop}{" "}
                        {index + 1}
                      </div>
                      <h4 className="mt-1 font-heading text-lg font-semibold">
                        {entry.place.name}
                      </h4>
                      <p className="mt-1 text-slate-600">
                        {entry.place.description}
                      </p>
                      <div className="mt-4">
                        <Photo
                          visual={visuals[entry.id]}
                          placeName={entry.place.name}
                          language={language}
                        />
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
                        <span className="rounded-full bg-blue-100 px-3 py-1 text-blue-800">
                          {labels.visit} ~
                          {entry.place.visit_minutes_estimate} {labels.minutes}
                        </span>
                        <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700">
                          {labels.travel} ~
                          {entry.place.travel_minutes_estimate} {labels.minutes}
                        </span>
                        <span className="rounded-full bg-blue-50 px-3 py-1 text-slate-700">
                          {labels.hours}:{" "}
                          {entry.place.opening_hours_verified
                            ? entry.place.opening_hours
                            : labels.unverified}
                        </span>
                      </div>
                      {entry.notes && (
                        <p className="mt-3 text-sm text-slate-600">
                          {entry.notes}
                        </p>
                      )}
                      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm">
                        {entry.place.source_references.map((source) => (
                          <a
                            className="inline-flex items-center gap-1 font-semibold text-accent underline-offset-4 hover:underline"
                            key={source.url}
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {source.title}
                            <ExternalLink size={14} />
                          </a>
                        ))}
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="text-slate-500">
                    {labels.noStops}
                  </p>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
function GraphView({
  svg,
  imageLoading,
  imageUnavailable,
  fallbackLoading,
  error,
  onImageLoad,
  onImageError,
  onBack,
  language,
}: {
  svg: string;
  imageLoading: boolean;
  imageUnavailable: boolean;
  fallbackLoading: boolean;
  error: LocalizedMessage;
  onImageLoad: () => void;
  onImageError: () => void;
  onBack: () => void;
  language: Language;
}) {
  const labels = text(language);
  return (
    <section aria-labelledby="graph-title" className="rise mt-8">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 font-semibold text-slate-700 hover:bg-blue-100"
      >
        <ArrowLeft size={18} />
        {labels.back}
      </button>
      <div className="mt-4 rounded-3xl border border-blue-100 bg-white p-5 shadow-sm sm:p-7">
        <p className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">
          <Network size={16} />
          {labels.readOnly}
        </p>
        <h1 id="graph-title" className="mt-4 font-heading text-2xl font-bold">
          {labels.graphTitle}
        </h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          {labels.graphDescription}
        </p>
        {!imageUnavailable && (
          <figure
            className="mt-6 min-h-72 overflow-hidden rounded-2xl border border-slate-300 bg-blue-50 p-3 sm:p-6"
            aria-busy={imageLoading}
          >
            {imageLoading && (
              <p className="flex items-center gap-2 text-slate-600" role="status">
                <LoaderCircle className="animate-spin" />
                {labels.graphLoading}
              </p>
            )}
            <img
              src="/api/graph/image"
              alt={labels.graphAlt}
              className="graph-image mx-auto max-h-[70dvh] max-w-full object-contain"
              decoding="async"
              onLoad={onImageLoad}
              onError={onImageError}
            />
            <figcaption className="mt-3 text-sm text-slate-600">
              {labels.graphCaption}
            </figcaption>
          </figure>
        )}
        {imageUnavailable && (
          <>
            <p
              className="mt-6 rounded-xl bg-amber-50 p-4 text-amber-900"
              role="status"
            >
              {labels.graphFallback}
            </p>
            {fallbackLoading && (
              <p className="mt-6 flex items-center gap-2 text-slate-600" role="status">
                <LoaderCircle className="animate-spin" />
                {labels.graphFallbackLoading}
              </p>
            )}
            {error && (
              <p
                className="mt-6 rounded-xl bg-red-50 p-4 text-red-800"
                role="alert"
              >
                {labels[error]}
              </p>
            )}
            {svg && (
              <div
                className="graph-svg mt-6 overflow-hidden rounded-2xl border border-slate-300 bg-blue-50 p-3 sm:p-6"
                role="img"
                aria-label={labels.graphAlt}
                dangerouslySetInnerHTML={{ __html: svg }}
              />
            )}
          </>
        )}
      </div>
    </section>
  );
}

function ChatBubble({
  role,
  content,
  issues = [],
  status,
  source_references = [],
  language,
}: Pick<ChatMessage, "role" | "content" | "issues" | "status" | "source_references"> & { language: Language }) {
  const labels = text(language);
  const agent = role === "agent";
  const statusLabel =
    status === "committed"
      ? labels.statusCommitted
      : status === "rejected"
        ? labels.statusRejected
        : status === "unchanged"
          ? labels.statusUnchanged
          : status === "provider_error"
            ? labels.statusProviderError
            : status;
  return (
    <div className={`flex ${agent ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[88%] ${agent ? "items-start" : "items-end"}`}>
        <div
          className={`mb-1 flex items-center gap-1.5 text-xs font-bold ${agent ? "text-slate-500" : "justify-end text-blue-700"}`}
        >
          {agent ? (
            <Bot size={13} aria-hidden="true" />
          ) : (
            <UserRound size={13} aria-hidden="true" />
          )}
          {agent ? labels.assistant : labels.you}
        </div>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm ${agent ? "rounded-tl-md bg-blue-50 text-slate-900" : "rounded-tr-md bg-primary text-white"}`}
        >
          <p className="whitespace-pre-wrap break-words">{content}</p>
          {status && (
            <p
              className={`mt-2 border-t pt-2 text-xs font-semibold ${agent ? "border-slate-300 text-slate-500" : "border-white/25 text-blue-900"}`}
            >
              {statusLabel}
            </p>
          )}
          {issues.length > 0 && (
            <ul
              className={`mt-2 list-disc space-y-1 border-t pt-2 pl-4 text-xs ${agent ? "border-slate-300 text-slate-600" : "border-white/25 text-blue-900"}`}
            >
              {issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
          {source_references.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 border-t border-slate-300 pt-2 text-xs">
              {source_references.map((source) => (
                <a
                  key={source.url}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-semibold text-accent hover:underline"
                >
                  {source.title}
                  <ExternalLink size={12} />
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ChatWidget({
  open,
  onOpenChange,
  state,
  message,
  setMessage,
  errors,
  setErrors,
  submitting,
  requestError,
  onSend,
  language,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  state: ApiState;
  message: string;
  setMessage: Dispatch<SetStateAction<string>>;
  errors: FormErrors;
  setErrors: Dispatch<SetStateAction<FormErrors>>;
  submitting: boolean;
  requestError: LocalizedMessage;
  onSend: (message: string) => Promise<boolean>;
  language: Language;
}) {
  const labels = text(language);
  const inputRef = useRef<HTMLInputElement>(null);
  const messages: ChatMessage[] = state.conversation.map((turn, index) => ({
    id: `session-${index}-${turn.role}`,
    role: turn.role === "assistant" ? "agent" : "user",
    content: turn.content,
    source_references: turn.source_references,
  }));

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => inputRef.current?.focus());
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [onOpenChange, open]);

  const submitChat = (event: FormEvent) => {
    event.preventDefault();
    if (!message.trim()) {
      setErrors((current) => ({
        ...current,
        chat: "chatRequired",
      }));
      return;
    }
    setErrors((current) => ({ ...current, chat: undefined }));
    const sent = message.trim();
    void onSend(sent).then((accepted) => {
      if (accepted) setMessage((current) => (current === sent ? "" : current));
    });
  };

  return (
    <>
      {open && (
        <section
          id="chat-panel"
          className="chat-panel fixed bottom-24 right-4 z-40 flex h-[min(620px,calc(100dvh-7rem))] w-[calc(100vw-2rem)] max-w-md flex-col overflow-hidden rounded-3xl border border-slate-300 bg-white shadow-2xl shadow-slate-900/10 sm:right-6"
          role="dialog"
          aria-labelledby="chat-panel-title"
        >
          <header className="flex items-center justify-between gap-3 border-b border-slate-700 bg-ink px-4 py-4 text-white sm:px-5">
            <div className="flex min-w-0 items-center gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-blue-600">
                <Bot aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h2 id="chat-panel-title" className="font-heading font-bold">
                  {labels.chatTitle}
                </h2>
                <p className="truncate text-sm text-slate-300">
                  {labels.chatSubtitle}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-xl text-slate-200 transition hover:bg-white/10 hover:text-white"
              aria-label={labels.closeChat}
              title={labels.closeChat}
            >
              <X size={20} aria-hidden="true" />
            </button>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
            <div className="space-y-4">
              {messages.length === 0 && (
                <>
                  <ChatBubble
                    role="agent"
                    content={labels.chatEmpty}
                    language={language}
                  />
                  <div className="ml-auto grid max-w-[88%] gap-2">
                  {labels.chatExamples.map((example) => (
                      <button
                        type="button"
                        key={example}
                        onClick={() => setMessage(example)}
                        className="min-h-11 rounded-xl border border-blue-200 bg-blue-50 px-3 text-left text-sm font-semibold text-slate-700 transition hover:border-primary hover:bg-blue-100"
                      >
                        {example}
                      </button>
                    ))}
                  </div>
                </>
              )}
              {messages.map((chatMessage) => (
                <ChatBubble key={chatMessage.id} {...chatMessage} language={language} />
              ))}
              {state.pending && (
                <div role="status" aria-live="polite">
                  <ChatBubble role="agent" content={labels.chatPending} language={language} />
                </div>
              )}
            </div>
            {requestError && (
              <p
                className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-800"
                role="alert"
              >
                {requestError}
              </p>
            )}
          </div>

          <form
            className="border-t border-slate-300 bg-blue-50 p-3 sm:p-4"
            onSubmit={submitChat}
          >
            <label className="sr-only" htmlFor="chat-widget-input">
              {labels.chatRequest}
            </label>
            <div className="flex items-end gap-2">
              <div className="min-w-0 flex-1">
                <input
                  ref={inputRef}
                  id="chat-widget-input"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  disabled={state.pending || submitting}
                  aria-invalid={Boolean(errors.chat)}
                  aria-describedby={errors.chat ? "chat-widget-error" : undefined}
                  className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base text-slate-900 placeholder:text-slate-500"
                  placeholder={labels.chatPlaceholder}
                />
                <span id="chat-widget-error">
                  <FieldError
                    message={errors.chat ? labels[errors.chat] : undefined}
                  />
                </span>
              </div>
              <button
                type="submit"
                disabled={state.pending || submitting || !message.trim()}
                className="inline-flex min-h-12 min-w-12 items-center justify-center rounded-xl bg-primary px-4 font-bold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={labels.send}
                title={labels.send}
              >
                {submitting || state.pending ? (
                  <LoaderCircle className="animate-spin" aria-hidden="true" />
                ) : (
                  <Send size={19} aria-hidden="true" />
                )}
                <span className="sr-only">{labels.send}</span>
              </button>
            </div>
          </form>
        </section>
      )}

      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className="fixed bottom-4 right-4 z-40 inline-flex min-h-14 min-w-14 items-center justify-center rounded-full bg-primary text-white shadow-xl shadow-blue-900/20 transition hover:-translate-y-0.5 hover:bg-blue-500 focus-visible:ring-4 focus-visible:ring-blue-400 sm:bottom-6 sm:right-6"
        aria-expanded={open}
        aria-controls="chat-panel"
        aria-label={open ? labels.closeChat : labels.openChat}
        title={open ? labels.closeChat : labels.openChat}
      >
        {open ? <X aria-hidden="true" /> : <MessageCircle aria-hidden="true" />}
        <span className="sr-only">{open ? labels.closeChat : labels.openChat}</span>
      </button>
    </>
  );
}

function SavedToursView({
  tours,
  selectedTour,
  loading,
  hasMore,
  error,
  loadingId,
  deletingId,
  onBack,
  onSelect,
  onDelete,
  onLoadMore,
  onClaim,
  claiming,
  claimStatus,
  language,
}: {
  tours: SavedTourSummary[];
  selectedTour: SavedTour | null;
  loading: boolean;
  hasMore: boolean;
  error: LocalizedMessage;
  loadingId: string | null;
  deletingId: string | null;
  onBack: () => void;
  onSelect: (id: string) => void;
  onDelete: (tour: SavedTourSummary) => void;
  onLoadMore: () => void;
  onClaim: () => void;
  claiming: boolean;
  claimStatus: LocalizedMessage;
  language: Language;
}) {
  const labels = text(language);
  const savedAt = (value: string) =>
    new Intl.DateTimeFormat(dateLocale(language), {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  return (
    <section aria-labelledby="saved-tours-title" className="rise mt-8">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 font-semibold text-slate-700 hover:bg-blue-100"
      >
        <ArrowLeft size={18} aria-hidden="true" />
        {labels.back}
      </button>
      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(17rem,.7fr)_minmax(0,1.3fr)]">
        <aside className="rounded-3xl border border-blue-100 bg-white p-5 shadow-sm sm:p-6">
          <h1 id="saved-tours-title" className="font-heading text-2xl font-bold">
            {labels.savedTours}
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">{labels.savedToursDescription}</p>
          <button
            type="button"
            onClick={onClaim}
            disabled={claiming}
            className="mt-4 inline-flex min-h-11 items-center rounded-xl border border-blue-200 px-4 text-sm font-semibold text-primary hover:bg-blue-50 disabled:opacity-50"
          >
            {claiming ? labels.claimingOldTours : labels.claimOldTours}
          </button>
          {claimStatus && <p className="mt-2 text-sm text-slate-700" role="status">{labels[claimStatus]}</p>}
          {loading && (
            <p className="mt-5 inline-flex items-center gap-2 text-sm text-slate-600" role="status">
              <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
              {labels.savedToursLoading}
            </p>
          )}
          {error && (
            <p className="mt-5 rounded-xl bg-red-50 p-3 text-sm text-red-800" role="alert">
              {labels[error]}
            </p>
          )}
          {!loading && !error && tours.length === 0 && (
            <p className="mt-5 rounded-xl bg-blue-50 p-4 text-sm leading-6 text-slate-700">
              {labels.savedToursEmpty}
            </p>
          )}
          <ul className="mt-5 space-y-3" aria-label={labels.savedTours}>
            {tours.map((tour) => {
              const selected = selectedTour?.id === tour.id;
              return (
                <li className="flex gap-2" key={tour.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(tour.id)}
                    aria-current={selected ? "page" : undefined}
                    aria-busy={loadingId === tour.id}
                    className={`min-h-11 min-w-0 flex-1 rounded-xl border p-3 text-left transition ${selected ? "border-primary bg-blue-50" : "border-slate-200 hover:border-blue-300 hover:bg-blue-50/50"}`}
                  >
                    <span className="flex items-center gap-2 font-semibold text-slate-900">
                      {tour.title}
                      {loadingId === tour.id && (
                        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                      )}
                    </span>
                    <span className="mt-1 block text-sm text-slate-600">
                      <time dateTime={tour.start_date}>
                        {formatDateOnly(tour.start_date, language)}
                      </time>
                      {" · "}
                      {tour.day_count} {labels.dayUnit} · v{tour.revision}
                    </span>
                    <span className="mt-1 block text-xs text-slate-500">
                      {labels.savedOn} {savedAt(tour.saved_at)}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(tour)}
                    disabled={deletingId === tour.id}
                    className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-xl text-slate-600 hover:bg-red-50 hover:text-red-800 disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label={`${labels.deleteSavedTour}: ${tour.title}`}
                    title={labels.deleteSavedTour}
                  >
                    {deletingId === tour.id ? (
                      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Trash2 className="size-4" aria-hidden="true" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
          {hasMore && (
            <button
              type="button"
              onClick={onLoadMore}
              disabled={loading}
              className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-blue-200 px-4 font-semibold text-primary transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
              {loading ? labels.savedToursLoadingMore : labels.savedToursLoadMore}
            </button>
          )}
        </aside>
        <div className="min-w-0">
          {selectedTour ? (
            <>
              <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950" role="note">
                {labels.savedTourStale}
              </p>
              <PlanView
                plan={selectedTour.plan}
                visuals={selectedTour.visuals_by_entry || {}}
                loading={false}
                language={language}
                statusLabel={labels.savedTourSnapshot}
                titleId="saved-tour-title"
              />
            </>
          ) : (
            <div className="rounded-3xl border border-dashed border-blue-200 bg-white/80 p-8 text-center text-slate-600">
              <Save className="mx-auto mb-3 text-primary" aria-hidden="true" />
              <p>{labels.savedToursSelect}</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function AdminUsersView({
  users,
  loading,
  hasMore,
  error,
  usageAvailable,
  status,
  updatingId,
  selectedUserId,
  usage,
  usageLoading,
  usageError,
  usageStart,
  usageEnd,
  language,
  onBack,
  onLoadMore,
  onChangeAccess,
  onSelectUser,
  onUsageStartChange,
  onUsageEndChange,
}: {
  users: AdminUser[];
  loading: boolean;
  hasMore: boolean;
  error: LocalizedMessage;
  usageAvailable: boolean;
  status: LocalizedMessage;
  updatingId: string | null;
  selectedUserId: string | null;
  usage: AdminUsage | null;
  usageLoading: boolean;
  usageError: LocalizedMessage;
  usageStart: string;
  usageEnd: string;
  language: Language;
  onBack: () => void;
  onLoadMore: () => void;
  onChangeAccess: (user: AdminUser) => void;
  onSelectUser: (id: string) => void;
  onUsageStartChange: (date: string) => void;
  onUsageEndChange: (date: string) => void;
}) {
  const labels = text(language);
  const numbers = new Intl.NumberFormat(dateLocale(language));
  const dollars = new Intl.NumberFormat(dateLocale(language), {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  });
  const cost = (value: number | string | null) => {
    if (value === null) return labels.adminCostUnknown;
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0
      ? dollars.format(parsed)
      : labels.adminCostUnknown;
  };
  return (
    <section className="rise" aria-labelledby="admin-title">
      <button type="button" onClick={onBack} className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 font-semibold text-slate-700 hover:bg-blue-100 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300">
        <ArrowLeft size={18} aria-hidden="true" />{labels.back}
      </button>
      <div className="mt-5 rounded-3xl border border-blue-100 bg-white p-5 shadow-sm sm:p-8">
        <h1 id="admin-title" className="font-heading text-2xl font-bold">{labels.adminUsers}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">{labels.adminUsageNote}</p>
        {error && <p className="mt-4 rounded-xl bg-red-50 p-4 text-red-800" role="alert">{labels[error]}</p>}
        {!usageAvailable && <p className="mt-4 rounded-xl bg-amber-50 p-4 text-amber-900" role="status">{labels.adminUsageUnavailable}</p>}
        {status && <p className="mt-4 rounded-xl bg-green-50 p-4 text-green-800" role="status">{labels[status]}</p>}
        {loading && users.length === 0 && <p className="mt-5 text-slate-600" role="status">{labels.adminLoading}</p>}
        {!loading && users.length === 0 && !error && <p className="mt-5 text-slate-600">{labels.adminEmpty}</p>}
        <ul className="mt-5 grid gap-4" aria-busy={loading}>
          {users.map((user) => (
            <li key={user.id} className="min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="break-all font-semibold text-slate-900">{user.email || user.id}</h2>
                  {user.email && <p className="mt-1 break-all text-xs text-slate-500">{user.id}</p>}
                  <p className="mt-1 text-sm text-slate-600">{labels.adminCreated}: {new Date(user.created_at).toLocaleDateString(dateLocale(language))}</p>
                </div>
                <span className={`rounded-full px-3 py-1 text-sm font-semibold ${user.access_status === "active" ? "bg-green-100 text-green-800" : user.access_status === "pending" ? "bg-amber-100 text-amber-900" : "bg-red-100 text-red-800"}`}>
                  {user.access_status === "active" ? labels.adminActive : user.access_status === "pending" ? labels.adminPending : labels.adminBlocked}
                </span>
              </div>
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div><dt className="text-slate-600">{labels.adminInputTokens}</dt><dd className="mt-1 font-semibold">{user.input_tokens === null ? "—" : numbers.format(user.input_tokens)}</dd></div>
                <div><dt className="text-slate-600">{labels.adminOutputTokens}</dt><dd className="mt-1 font-semibold">{user.output_tokens === null ? "—" : numbers.format(user.output_tokens)}</dd></div>
                <div><dt className="text-slate-600">{labels.adminEstimatedCost}</dt><dd className="mt-1 font-semibold">{cost(user.estimated_cost_usd)}</dd></div>
              </dl>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                {user.is_admin && <span className="text-sm font-semibold text-blue-700">{labels.adminRole}</span>}
                <button
                  type="button"
                  onClick={() => onChangeAccess(user)}
                  disabled={updatingId !== null || user.is_admin}
                  className={`inline-flex min-h-11 items-center rounded-xl px-4 text-sm font-bold focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300 disabled:cursor-not-allowed disabled:opacity-50 ${user.access_status === "active" ? "border border-red-200 bg-white text-red-800 hover:bg-red-50" : "bg-primary text-white hover:bg-blue-500"}`}
                >
                  {updatingId === user.id ? labels.adminUpdating : user.access_status === "active" ? labels.adminBlock : labels.adminGrant}
                </button>
                <button type="button" onClick={() => onSelectUser(user.id)} aria-expanded={selectedUserId === user.id} className="inline-flex min-h-11 items-center rounded-xl px-4 text-sm font-semibold text-blue-800 hover:bg-blue-100 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300">
                  {labels.adminUsageDetail}
                </button>
              </div>
              {selectedUserId === user.id && <section className="mt-5 rounded-2xl border border-blue-100 bg-white p-4" aria-label={labels.adminUsageDetail}>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="text-sm font-semibold text-slate-700">{labels.adminFromDate}
                    <input type="date" value={usageStart} max={usageEnd} onChange={(event) => onUsageStartChange(event.target.value)} className="mt-1 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3" />
                  </label>
                  <label className="text-sm font-semibold text-slate-700">{labels.adminToDate}
                    <input type="date" value={usageEnd} min={usageStart} max={today} onChange={(event) => onUsageEndChange(event.target.value)} className="mt-1 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3" />
                  </label>
                </div>
                {usageError && <p className="mt-3 text-sm text-red-800" role="alert">{labels[usageError]}</p>}
                {usageLoading && <p className="mt-3 text-sm text-slate-600" role="status">{labels.adminLoadingUsage}</p>}
                {usage && !usageLoading && <>
                  <dl className="mt-4 grid gap-3 border-b border-slate-200 pb-4 text-sm sm:grid-cols-4">
                    <div><dt className="text-slate-600">{labels.adminInputTokens}</dt><dd className="font-semibold">{numbers.format(usage.input_tokens)}</dd></div>
                    <div><dt className="text-slate-600">{labels.adminOutputTokens}</dt><dd className="font-semibold">{numbers.format(usage.output_tokens)}</dd></div>
                    <div><dt className="text-slate-600">{labels.adminEstimatedCost}</dt><dd className="font-semibold">{cost(usage.estimated_cost_usd)}</dd></div>
                    <div><dt className="text-slate-600">{labels.adminUnpricedCalls}</dt><dd className="font-semibold">{numbers.format(usage.unpriced_calls)}</dd></div>
                  </dl>
                  {usage.by_model.length === 0 ? <p className="mt-4 text-sm text-slate-600">{labels.adminNoUsage}</p> : <ul className="mt-4 grid gap-3">
                    {usage.by_model.map((model) => <li key={`${model.provider}:${model.model}:${model.role}`} className="min-w-0 rounded-xl bg-slate-50 p-3 text-sm">
                      <p className="break-all font-semibold">{model.provider} · {model.model} · {model.role}</p>
                      <p className="mt-1 text-slate-700">{labels.adminInputTokens}: {numbers.format(model.input_tokens)} · {labels.adminOutputTokens}: {numbers.format(model.output_tokens)}</p>
                      <p className="mt-1 text-slate-700">{labels.adminEstimatedCost}: {cost(model.estimated_cost_usd)} · {labels.adminUnpricedCalls}: {numbers.format(model.unpriced_calls)}</p>
                    </li>)}
                  </ul>}
                </>}
              </section>}
            </li>
          ))}
        </ul>
        {hasMore && <button type="button" onClick={onLoadMore} disabled={loading} className="mt-6 inline-flex min-h-11 items-center rounded-xl border border-blue-200 px-4 font-semibold text-blue-800 hover:bg-blue-50 disabled:opacity-50">{loading ? labels.adminLoading : labels.adminLoadMore}</button>}
      </div>
    </section>
  );
}

function App() {
  const [landingLanguage, setLandingLanguage] = useState<Language>(() =>
    new URLSearchParams(window.location.search).get("lang") === "en" ? "en" : "vi",
  );
  const [state, setState] = useState<ApiState>({
    language: "vi",
    plan: null,
    pending: false,
    response: null,
    conversation: [],
  });
  const [destination, setDestination] = useState("");
  const [startDate, setStartDate] = useState(today);
  const [days, setDays] = useState(2);
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [requestError, setRequestError] = useState<LocalizedMessage>("");
  const [submitting, setSubmitting] = useState(false);
  const [visuals, setVisuals] = useState<Record<string, Visual>>({});
  const [visualsLoading, setVisualsLoading] = useState(false);
  const [view, setView] = useState<View>("itinerary");
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [authError, setAuthError] = useState<LocalizedMessage>("");
  const [signingOut, setSigningOut] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [graphSvg, setGraphSvg] = useState("");
  const [graphImageLoading, setGraphImageLoading] = useState(true);
  const [graphImageUnavailable, setGraphImageUnavailable] = useState(false);
  const [graphFallbackLoading, setGraphFallbackLoading] = useState(false);
  const [graphError, setGraphError] = useState<LocalizedMessage>("");
  const [savedTours, setSavedTours] = useState<SavedTourSummary[]>([]);
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminUsersLoading, setAdminUsersLoading] = useState(false);
  const [adminUsersHasMore, setAdminUsersHasMore] = useState(false);
  const [adminUsersCursor, setAdminUsersCursor] = useState<string | null>(null);
  const [adminUsersError, setAdminUsersError] = useState<LocalizedMessage>("");
  const [adminUsageAvailable, setAdminUsageAvailable] = useState(true);
  const [adminUsersStatus, setAdminUsersStatus] = useState<LocalizedMessage>("");
  const [adminUserUpdatingId, setAdminUserUpdatingId] = useState<string | null>(null);
  const adminUsersRequest = useRef(0);
  const [selectedAdminUserId, setSelectedAdminUserId] = useState<string | null>(null);
  const [adminUsage, setAdminUsage] = useState<AdminUsage | null>(null);
  const [adminUsageLoading, setAdminUsageLoading] = useState(false);
  const [adminUsageError, setAdminUsageError] = useState<LocalizedMessage>("");
  const [adminUsageStart, setAdminUsageStart] = useState(currentMonthStart);
  const [adminUsageEnd, setAdminUsageEnd] = useState(today);
  const adminUsageRequest = useRef(0);
  const [savedToursLoading, setSavedToursLoading] = useState(false);
  const [savedToursHasMore, setSavedToursHasMore] = useState(false);
  const [savedToursCursor, setSavedToursCursor] = useState<string | null>(null);
  const savedToursRequest = useRef(0);
  const [savedToursError, setSavedToursError] = useState<LocalizedMessage>("");
  const [selectedSavedTour, setSelectedSavedTour] = useState<SavedTour | null>(null);
  const [savedTourLoadingId, setSavedTourLoadingId] = useState<string | null>(null);
  const [savedTourDeletingId, setSavedTourDeletingId] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<LocalizedMessage>("");
  const [savingTour, setSavingTour] = useState(false);
  const [claimingTours, setClaimingTours] = useState(false);
  const [claimStatus, setClaimStatus] = useState<LocalizedMessage>("");
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const accountTriggerRef = useRef<HTMLButtonElement>(null);
  const authRecheckInFlight = useRef(false);
  const currentSessionLanguage = useRef<Language>("vi");
  const activeLanguage = auth?.authenticated && auth.access_status === "active"
    ? state.language : landingLanguage;
  const labels = text(activeLanguage);
  const accountName = auth?.authenticated
    ? auth.email?.split("@")[0]?.trim() || labels.account
    : labels.account;
  useEffect(() => {
    document.documentElement.lang = dateLocale(activeLanguage);
    document.title = labels.pageTitle;
    document
      .querySelector('meta[name="description"]')
      ?.setAttribute("content", labels.metaDescription);
  }, [activeLanguage]);
  useEffect(() => {
    currentSessionLanguage.current = state.language;
  }, [state.language]);
  const load = async (csrfToken = auth?.csrf_token || "") => {
    try {
      setState(await api<ApiState>("/api/session"));
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      clearPrivateWorkspace();
      await api<ApiState>("/api/session", {
        method: "POST",
        headers: { "X-CSRF-Token": csrfToken || "" },
      });
      setState(await api<ApiState>("/api/session"));
    }
  };
  const clearPrivateWorkspace = () => {
    setState({
      language: currentSessionLanguage.current,
      plan: null,
      pending: false,
      response: null,
      conversation: [],
    });
    setDestination("");
    setStartDate(today);
    setDays(2);
    setMessage("");
    setErrors({});
    setRequestError("");
    setVisuals({});
    setVisualsLoading(false);
    setView("itinerary");
    setChatOpen(false);
    setSavedTours([]);
    setSelectedSavedTour(null);
    setSavedToursCursor(null);
    setSavedToursHasMore(false);
    savedToursRequest.current += 1;
    setAdminUsers([]);
    setAdminUsersCursor(null);
    setAdminUsersHasMore(false);
    setAdminUsersLoading(false);
    setAdminUsersError("");
    setAdminUsageAvailable(true);
    setAdminUsersStatus("");
    setAdminUserUpdatingId(null);
    adminUsersRequest.current += 1;
    setSelectedAdminUserId(null);
    setAdminUsage(null);
    setAdminUsageLoading(false);
    setAdminUsageError("");
    adminUsageRequest.current += 1;
  };
  const recheckAuth = async (readDeepLink: boolean) => {
    if (authRecheckInFlight.current) return;
    authRecheckInFlight.current = true;
    if (!readDeepLink) setLandingLanguage(currentSessionLanguage.current);
    setAuth(null);
    try {
      const current = await api<AuthState>("/api/auth/me");
      if (!current.authenticated) {
        clearPrivateWorkspace();
        setAuth(current);
        return;
      }
      if (current.access_status === "pending") {
        clearPrivateWorkspace();
        setAuth(current);
        return;
      }
      if (!current.is_admin && view === "admin") setView("itinerary");
      await load(current.csrf_token);
      const parameters = new URLSearchParams(window.location.search);
      const requestedLanguage = parameters.get("lang");
      if (readDeepLink && (requestedLanguage === "en" || requestedLanguage === "vi")) {
        const updated = await api<ApiState>("/api/session/language", {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": current.csrf_token || "",
          },
          body: JSON.stringify({ language: requestedLanguage }),
        });
        setState(updated);
        setLandingLanguage(requestedLanguage);
      }
      if (readDeepLink && parameters.get("view") === "saved") {
        setView("saved");
      }
      if (readDeepLink && parameters.get("view") === "admin" && current.is_admin) {
        setView("admin");
      }
      if (readDeepLink && (parameters.has("view") || parameters.has("lang"))) {
        window.history.replaceState(null, "", "/");
      }
      setAuth(current);
    } catch (error) {
      clearPrivateWorkspace();
      setAuth({ authenticated: false });
      setAuthError("authError");
      setRequestError(apiErrorMessageKey(error, "errorStart"));
    } finally {
      authRecheckInFlight.current = false;
    }
  };
  useEffect(() => {
    const parameters = new URLSearchParams(window.location.search);
    if (parameters.has("auth_error")) {
      setAuthError("authError");
      parameters.delete("auth_error");
      const query = parameters.toString();
      window.history.replaceState(null, "", query ? `/?${query}` : "/");
    }
    void recheckAuth(true);
  }, []);
  useEffect(() => {
    const recheckOnFocus = () => void recheckAuth(false);
    const recheckOnVisibility = () => {
      if (document.visibilityState === "visible") recheckOnFocus();
    };
    window.addEventListener("focus", recheckOnFocus);
    document.addEventListener("visibilitychange", recheckOnVisibility);
    return () => {
      window.removeEventListener("focus", recheckOnFocus);
      document.removeEventListener("visibilitychange", recheckOnVisibility);
    };
  }, []);
  useEffect(() => {
    if (!state.pending) return;
    const timer = window.setInterval(() => void load(), 1200);
    return () => window.clearInterval(timer);
  }, [state.pending]);
  useEffect(() => {
    if (!accountOpen) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!accountMenuRef.current?.contains(event.target as Node)) {
        setAccountOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      setAccountOpen(false);
      accountTriggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [accountOpen]);
  useEffect(() => {
    const plan = state.plan;
    if (!plan) {
      setVisuals({});
      return;
    }
    if (state.visuals_by_entry) {
      setVisuals(state.visuals_by_entry);
      return;
    }
    let active = true;
    setVisualsLoading(true);
    void api<{ visuals_by_entry: Record<string, Visual> }>(
      `/api/visuals?revision=${plan.revision}`,
    )
      .then((result) => {
        if (active) setVisuals(result.visuals_by_entry);
      })
      .catch(() => {
        if (active) setVisuals({});
      })
      .finally(() => {
        if (active) setVisualsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [state.plan?.revision, state.visuals_by_entry]);
  useEffect(() => {
    if (!graphImageUnavailable || graphSvg || graphFallbackLoading) return;
    setGraphFallbackLoading(true);
    setGraphError("");
    void api<{ svg: string }>("/api/graph")
      .then((result) => setGraphSvg(result.svg))
      .catch(() => setGraphError("errorGraph"))
      .finally(() => setGraphFallbackLoading(false));
  }, [graphFallbackLoading, graphImageUnavailable, graphSvg]);
  const submit = async (body: object) => {
    setRequestError("");
    setSubmitting(true);
    try {
      await api<{ accepted: boolean }>("/api/turns", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": auth?.csrf_token || "",
        },
        body: JSON.stringify(body),
      });
      await load();
      return true;
    } catch (error) {
      setRequestError(apiErrorMessageKey(error, "errorSend"));
      return false;
    } finally {
      setSubmitting(false);
    }
  };
  const loadSavedTours = async (append = false) => {
    if (!auth?.authenticated) return;
    if (append && (!savedToursCursor || savedToursLoading)) return;
    const request = ++savedToursRequest.current;
    const cursor = append ? `&cursor=${encodeURIComponent(savedToursCursor!)}` : "";
    if (!append) {
      setSavedToursCursor(null);
      setSavedToursHasMore(false);
    }
    setSavedToursLoading(true);
    setSavedToursError("");
    try {
      const result = await api<SavedTourPage>(
        `/api/saved-tours?limit=${savedToursPageSize}${cursor}`,
      );
      if (request !== savedToursRequest.current) return;
      setSavedTours((current) => append
        ? [...current, ...result.items.filter((tour) => !current.some((item) => item.id === tour.id))]
        : result.items);
      if (!append) {
        setSelectedSavedTour((selected) =>
          selected && result.items.some((tour) => tour.id === selected.id) ? selected : null,
        );
      }
      setSavedToursCursor(result.next_cursor);
      setSavedToursHasMore(result.has_more && result.next_cursor !== null);
    } catch {
      const current = await api<AuthState>("/api/auth/me").catch(() => null);
      if (current) setAuth(current);
      if (request === savedToursRequest.current) setSavedToursError("errorSavedTours");
    } finally {
      if (request === savedToursRequest.current) setSavedToursLoading(false);
    }
  };
  const openSavedTours = () => {
    setAccountOpen(false);
    setView("saved");
  };
  useEffect(() => {
    if (view === "saved" && auth?.authenticated) void loadSavedTours(false);
  }, [view, auth?.authenticated]);
  const loadAdminUsers = async (append = false) => {
    if (!auth?.is_admin || auth.access_status !== "active") return;
    if (append && (!adminUsersCursor || adminUsersLoading)) return;
    const request = ++adminUsersRequest.current;
    const cursor = append ? `&cursor=${encodeURIComponent(adminUsersCursor!)}` : "";
    if (!append) {
      setAdminUsersCursor(null);
      setAdminUsersHasMore(false);
      setAdminUsageAvailable(true);
    }
    setAdminUsersLoading(true);
    setAdminUsersError("");
    try {
      const result = await api<AdminUsersPage>(`/api/admin/users?limit=${adminUsersPageSize}${cursor}`);
      if (request !== adminUsersRequest.current) return;
      setAdminUsers((current) => append
        ? [...current, ...result.items.filter((user) => !current.some((item) => item.id === user.id))]
        : result.items);
      setAdminUsersCursor(result.next_cursor);
      setAdminUsageAvailable((current) => append ? current && result.usage_available : result.usage_available);
      setAdminUsersHasMore(result.has_more && result.next_cursor !== null);
    } catch {
      if (request === adminUsersRequest.current) setAdminUsersError("adminLoadError");
    } finally {
      if (request === adminUsersRequest.current) setAdminUsersLoading(false);
    }
  };
  useEffect(() => {
    if (view === "admin" && auth?.is_admin) void loadAdminUsers(false);
  }, [view, auth?.is_admin]);
  useEffect(() => {
    if (view !== "admin" || !auth?.is_admin || !selectedAdminUserId) return;
    const request = ++adminUsageRequest.current;
    setAdminUsage(null);
    if (!adminUsageStart || !adminUsageEnd || adminUsageStart > adminUsageEnd) {
      setAdminUsageLoading(false);
      setAdminUsageError("adminDateError");
      return;
    }
    setAdminUsageLoading(true);
    setAdminUsageError("");
    void api<AdminUsage>(`/api/admin/users/${encodeURIComponent(selectedAdminUserId)}/usage?start=${encodeURIComponent(adminUsageStart)}&end=${encodeURIComponent(adminUsageEnd)}`)
      .then((result) => { if (request === adminUsageRequest.current) setAdminUsage(result); })
      .catch(() => { if (request === adminUsageRequest.current) setAdminUsageError("adminUsageError"); })
      .finally(() => { if (request === adminUsageRequest.current) setAdminUsageLoading(false); });
  }, [view, auth?.is_admin, selectedAdminUserId, adminUsageStart, adminUsageEnd]);
  const changeAdminAccess = async (user: AdminUser) => {
    if (!auth?.csrf_token || adminUserUpdatingId) return;
    const access_status = user.access_status === "active" ? "blocked" : "active";
    const confirmation = access_status === "blocked" ? labels.adminConfirmBlock : labels.adminConfirmGrant;
    if (!window.confirm(confirmation)) return;
    const request = adminUsersRequest.current;
    setAdminUserUpdatingId(user.id);
    setAdminUsersError("");
    setAdminUsersStatus("");
    try {
      await api<unknown>(`/api/admin/users/${encodeURIComponent(user.id)}/access`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": auth.csrf_token },
        body: JSON.stringify({ access_status }),
      });
      if (request !== adminUsersRequest.current) return;
      setAdminUsers((current) => current.map((item) => item.id === user.id ? { ...item, access_status } : item));
      setAdminUsersStatus("adminAccessUpdated");
    } catch {
      if (request === adminUsersRequest.current) setAdminUsersError("adminUpdateError");
    } finally {
      if (request === adminUsersRequest.current) setAdminUserUpdatingId(null);
    }
  };
  const signIn = (returnTo = "/", intent: "login" | "signup" = "login") => {
    setAccountOpen(false);
    const separator = returnTo.includes("?") ? "&" : "?";
    const localizedReturnTo = `${returnTo}${separator}lang=${landingLanguage}`;
    const query = new URLSearchParams({ return_to: localizedReturnTo });
    if (intent === "signup") query.set("intent", "signup");
    window.location.assign(`/api/auth/login?${query.toString()}`);
  };
  const signOut = async () => {
    if (!auth?.csrf_token || signingOut) return;
    setSigningOut(true);
    setAuthError("");
    try {
      const result = await api<{ logout_url: string }>("/api/auth/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": auth.csrf_token },
      });
      setAuth({ authenticated: false });
      setSavedTours([]);
      setSelectedSavedTour(null);
      setSavedToursCursor(null);
      setSavedToursHasMore(false);
      savedToursRequest.current += 1;
      setAdminUsers([]);
      setAdminUsersCursor(null);
      setAdminUsersHasMore(false);
      adminUsersRequest.current += 1;
      window.location.assign(result.logout_url);
    } catch {
      setAuthError("signOutError");
    } finally {
      setSigningOut(false);
    }
  };
  const selectSavedTour = async (id: string) => {
    setSavedTourLoadingId(id);
    setSavedToursError("");
    try {
      setSelectedSavedTour(await api<SavedTour>(`/api/saved-tours/${id}`));
    } catch {
      setSavedToursError("errorSavedTours");
    } finally {
      setSavedTourLoadingId(null);
    }
  };
  const saveTour = async () => {
    if (!state.plan || state.pending || savingTour) return;
    if (!auth?.authenticated) {
      signIn("/");
      return;
    }
    setSavingTour(true);
    setSaveStatus("");
    try {
      const saved = await api<SavedTour>("/api/saved-tours", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": auth.csrf_token || "" },
        body: JSON.stringify({}),
      });
      setSavedTours((tours) => [saved, ...tours.filter((tour) => tour.id !== saved.id)]);
      setSaveStatus("saveTourSuccess");
    } catch {
      const current = await api<AuthState>("/api/auth/me").catch(() => null);
      if (current) setAuth(current);
      setSaveStatus("errorSaveTour");
    } finally {
      setSavingTour(false);
    }
  };
  const deleteSavedTour = async (tour: SavedTourSummary) => {
    if (!window.confirm(labels.confirmDeleteSavedTour)) return;
    setSavedTourDeletingId(tour.id);
    setSavedToursError("");
    try {
      await api<void>(`/api/saved-tours/${tour.id}`, {
        method: "DELETE",
        headers: { "X-CSRF-Token": auth?.csrf_token || "" },
      });
      setSavedTours((tours) => tours.filter((item) => item.id !== tour.id));
      if (selectedSavedTour?.id === tour.id) setSelectedSavedTour(null);
    } catch {
      setSavedToursError("errorDeleteSavedTour");
    } finally {
      setSavedTourDeletingId(null);
    }
  };
  const claimOldTours = async () => {
    if (!auth?.csrf_token || claimingTours) return;
    setClaimingTours(true);
    setClaimStatus("");
    try {
      const result = await api<ClaimResult>("/api/saved-tours/claim", {
        method: "POST",
        headers: { "X-CSRF-Token": auth.csrf_token },
      });
      setClaimStatus(result.conflicts.length > 0
        ? "claimOldToursConflict"
        : result.claimed_count > 0
          ? "claimOldToursDone"
          : "claimOldToursNone");
      if (result.claimed_count > 0) await loadSavedTours(false);
    } catch {
      setClaimStatus("claimOldToursError");
    } finally {
      setClaimingTours(false);
    }
  };
  const makePlan = (event: FormEvent) => {
    event.preventDefault();
    const next: FormErrors = {};
    if (!destination.trim())
      next.destination = "requiredDestination";
    if (!startDate) next.startDate = "requiredStartDate";
    if (!Number.isInteger(days) || days < 1 || days > 7)
      next.days = "requiredDays";
    setErrors(next);
    if (Object.keys(next).length) return;
    void submit({
      message: state.language === "en" ? `Create a ${days}-day sightseeing itinerary in ${destination.trim()}, starting on ${startDate}.` : `Hãy tạo lịch trình tham quan ${days} ngày tại ${destination.trim()}, bắt đầu ngày ${startDate}.`,
      request: {
        destination: destination.trim(),
        start_date: startDate,
        day_count: days,
      },
    });
  };
  const graphImageFailed = () => {
    setGraphImageLoading(false);
    setGraphImageUnavailable(true);
  };
  const reset = async () => {
    if (state.pending || submitting) return;
    if (state.plan && !window.confirm(labels.confirmReset)) return;
    setRequestError("");
    try {
      const replacement = await api<ApiState>("/api/session/reset", {
        method: "POST",
        headers: { "X-CSRF-Token": auth?.csrf_token || "" },
      });
      setState(replacement);
      setDestination("");
      setStartDate(today);
      setDays(2);
      setMessage("");
      setErrors({});
      setVisuals({});
      setVisualsLoading(false);
      setChatOpen(false);
      setSaveStatus("");
      setSelectedSavedTour(null);
      setView("itinerary");
      window.history.replaceState(null, "", "/");
    } catch (error) {
      setRequestError(apiErrorMessageKey(error, "errorReset"));
    }
  };
  const changeLanguage = async (language: Language) => {
    if (!auth?.authenticated || auth.access_status === "pending") {
      setLandingLanguage(language);
      return;
    }
    if (language === state.language) return;
    try {
      const updated = await api<ApiState>("/api/session/language", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": auth.csrf_token || "",
        },
        body: JSON.stringify({ language }),
      });
      setState(updated);
      setRequestError("");
    } catch (error) {
      setRequestError(apiErrorMessageKey(error, "errorConnection"));
    }
  };
  if (!auth?.authenticated) {
    return (
      <div className="min-h-dvh bg-gradient-to-b from-blue-50 via-white to-white text-slate-900">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 rounded bg-white p-3">
          {labels.skip}
        </a>
        <header className="border-b border-blue-100 bg-white/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
            <div className="flex items-center gap-3 font-heading font-bold">
              <span className="grid size-10 place-items-center rounded-2xl bg-primary text-white"><Compass aria-hidden="true" /></span>
              <span>{labels.brand}</span>
            </div>
            <div className="inline-flex items-center rounded-xl border border-blue-100 bg-blue-50/70 p-1" role="group" aria-label={labels.language}>
              <button type="button" aria-label={labels.switchToVietnamese} aria-pressed={landingLanguage === "vi"} onClick={() => void changeLanguage("vi")} className={`min-h-10 min-w-11 rounded-lg px-2 text-sm font-bold transition-colors ${landingLanguage === "vi" ? "bg-primary text-white shadow-sm" : "text-slate-700 hover:bg-white"}`}>VI</button>
              <button type="button" aria-label={labels.switchToEnglish} aria-pressed={landingLanguage === "en"} onClick={() => void changeLanguage("en")} className={`min-h-10 min-w-11 rounded-lg px-2 text-sm font-bold transition-colors ${landingLanguage === "en" ? "bg-primary text-white shadow-sm" : "text-slate-700 hover:bg-white"}`}>EN</button>
            </div>
          </div>
        </header>
        <main id="main" className="mx-auto grid min-h-[calc(100dvh-73px)] max-w-7xl items-center gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.15fr_.85fr] lg:py-20">
          <section className="rise max-w-2xl">
            <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold text-blue-800"><ShieldCheck size={16} aria-hidden="true" />{labels.landingEyebrow}</p>
            <h1 className="font-heading text-4xl font-bold tracking-tight sm:text-6xl">{labels.landingTitle}</h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-slate-700">{labels.landingDescription}</p>
            <ul className="mt-8 grid gap-3 text-slate-700" aria-label={labels.landingEyebrow}>
              <li className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 shrink-0 text-primary" size={20} aria-hidden="true" />{labels.landingEvidence}</li>
              <li className="flex items-start gap-3"><MessageCircle className="mt-0.5 shrink-0 text-primary" size={20} aria-hidden="true" />{labels.landingChat}</li>
            </ul>
          </section>
          <section className="rise rounded-3xl bg-white p-7 shadow-xl shadow-blue-900/10 ring-1 ring-blue-100 sm:p-9" aria-labelledby="landing-action-title">
            <Compass className="size-9 text-primary" aria-hidden="true" />
            <h2 id="landing-action-title" className="mt-5 font-heading text-2xl font-bold">{labels.landingActionTitle}</h2>
            <p className="mt-3 leading-7 text-slate-700">{auth === null ? labels.authChecking : labels.landingAccess}</p>
            {authError && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-800" role="alert">{labels[authError]}</p>}
            {auth !== null && <div className="mt-7 grid gap-3">
              <button type="button" onClick={() => signIn("/", "login")} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary px-5 font-bold text-white shadow-lg shadow-blue-500/25 transition hover:bg-blue-500 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300"><LogIn size={18} aria-hidden="true" />{labels.signInWithSso}</button>
              <button type="button" onClick={() => signIn("/", "signup")} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border border-blue-200 bg-white px-5 font-bold text-blue-800 transition hover:bg-blue-50 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300"><UserPlus size={18} aria-hidden="true" />{labels.register}</button>
            </div>}
          </section>
        </main>
      </div>
    );
  }
  if (auth.access_status === "pending") {
    return (
      <div className="min-h-dvh bg-gradient-to-b from-blue-50 via-white to-white text-slate-900">
        <header className="border-b border-blue-100 bg-white/90">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
            <span className="font-heading font-bold">{labels.brand}</span>
            <div className="inline-flex gap-2" role="group" aria-label={labels.language}>
              <button type="button" onClick={() => setLandingLanguage("vi")} aria-pressed={landingLanguage === "vi"} className="min-h-11 min-w-11 rounded-lg border border-blue-100 px-2 font-bold focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300">VI</button>
              <button type="button" onClick={() => setLandingLanguage("en")} aria-pressed={landingLanguage === "en"} className="min-h-11 min-w-11 rounded-lg border border-blue-100 px-2 font-bold focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300">EN</button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-xl px-4 py-16 sm:px-6">
          <section className="rounded-3xl border border-blue-100 bg-white p-7 shadow-sm" aria-labelledby="approval-title">
            <ShieldCheck className="text-primary" aria-hidden="true" />
            <h1 id="approval-title" className="mt-4 font-heading text-2xl font-bold">{labels.adminPending}</h1>
            <p className="mt-3 text-slate-700">{labels.approvalPending}</p>
            <p className="mt-2 break-all text-sm text-slate-600">{auth.email}</p>
            {authError && <p className="mt-4 text-red-800" role="alert">{labels[authError]}</p>}
            <button type="button" onClick={() => window.location.assign(`/?lang=${landingLanguage}`)} className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-primary px-4 font-semibold text-white hover:bg-blue-500 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300">{labels.approvalRefresh}</button>
            <button type="button" onClick={() => void signOut()} disabled={signingOut} className="ml-2 mt-3 inline-flex min-h-11 items-center rounded-xl border border-blue-200 px-4 font-semibold text-slate-700 hover:bg-blue-50 disabled:opacity-50">{signingOut ? labels.signingOut : labels.signOut}</button>
          </section>
        </main>
      </div>
    );
  }
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 rounded bg-white p-3"
      >
        {labels.skip}
      </a>
      <header className="border-b border-blue-100 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <button
            type="button"
            onClick={() => void reset()}
            disabled={state.pending || submitting}
            aria-label={labels.home}
            className="flex items-center gap-3 rounded-xl font-heading font-bold disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className="grid size-10 place-items-center rounded-2xl bg-primary text-white">
              <Compass />
            </span>
            <span>{labels.brand}</span>
          </button>
          <div className="flex items-center gap-1">
            <div
              className="inline-flex items-center rounded-xl border border-blue-100 bg-blue-50/70 p-1"
              role="group"
              aria-label={labels.language}
            >
              <button
                type="button"
                aria-label={labels.switchToVietnamese}
                aria-pressed={state.language === "vi"}
                title={labels.switchToVietnamese}
                onClick={() => void changeLanguage("vi")}
                className={`min-h-9 min-w-10 rounded-lg px-2 text-sm font-bold transition-colors ${state.language === "vi" ? "bg-primary text-white shadow-sm" : "text-slate-700 hover:bg-white"}`}
              >
                <span className="sm:hidden">VI</span>
                <span className="hidden sm:inline">{labels.languageVietnamese}</span>
              </button>
              <button
                type="button"
                aria-label={labels.switchToEnglish}
                aria-pressed={state.language === "en"}
                title={labels.switchToEnglish}
                onClick={() => void changeLanguage("en")}
                className={`min-h-9 min-w-10 rounded-lg px-2 text-sm font-bold transition-colors ${state.language === "en" ? "bg-primary text-white shadow-sm" : "text-slate-700 hover:bg-white"}`}
              >
                <span className="sm:hidden">EN</span>
                <span className="hidden sm:inline">{labels.languageEnglish}</span>
              </button>
            </div>
            <div className="relative" ref={accountMenuRef}>
              <button
                ref={accountTriggerRef}
                type="button"
                aria-label={
                  auth?.authenticated
                    ? `${labels.account}: ${accountName}`
                    : labels.account
                }
                aria-expanded={accountOpen}
                aria-controls="account-panel"
                onClick={() => setAccountOpen((open) => !open)}
                className="inline-flex min-h-11 max-w-40 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-slate-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300 sm:max-w-56"
              >
                <UserRound size={17} className="shrink-0" aria-hidden="true" />
                <span className="hidden truncate sm:inline">{accountName}</span>
                <ChevronDown
                  size={15}
                  className={`shrink-0 transition-transform ${accountOpen ? "rotate-180" : ""}`}
                  aria-hidden="true"
                />
              </button>
              <div
                id="account-panel"
                hidden={!accountOpen}
                aria-busy={signingOut}
                className="absolute right-0 z-30 mt-2 w-64 rounded-2xl border border-blue-100 bg-white p-2 shadow-lg shadow-blue-900/15"
              >
                {auth?.authenticated && (
                  <div className="border-b border-blue-100 px-3 py-2">
                    <p className="text-sm font-semibold text-slate-900">
                      {accountName}
                    </p>
                    <p
                      className="truncate text-sm text-slate-600"
                      title={auth.email}
                    >
                      {auth.email}
                    </p>
                  </div>
                )}
                <div className="pt-1">
                    <button
                      type="button"
                      onClick={openSavedTours}
                      disabled={signingOut}
                      className="flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-left text-sm font-semibold text-slate-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Save size={17} aria-hidden="true" />
                      {labels.savedTours}
                    </button>
                    {auth.is_admin && <button
                      type="button"
                      onClick={() => { setAccountOpen(false); setView("admin"); }}
                      disabled={signingOut}
                      className="flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-left text-sm font-semibold text-slate-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300 disabled:opacity-50"
                    >
                      <UsersRound size={17} aria-hidden="true" />
                      {labels.adminUsers}
                    </button>}
                    {auth?.authenticated ? (
                      <button
                        type="button"
                        onClick={() => void signOut()}
                        disabled={signingOut}
                        className="flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-left text-sm font-semibold text-slate-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300 disabled:opacity-50"
                      >
                        {signingOut ? (
                          <LoaderCircle size={17} className="animate-spin" aria-hidden="true" />
                        ) : (
                          <LogOut size={17} aria-hidden="true" />
                        )}
                        {signingOut ? labels.signingOut : labels.signOut}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => signIn("/")}
                        className="flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-left text-sm font-semibold text-slate-700 hover:bg-blue-50 focus-visible:outline focus-visible:outline-4 focus-visible:outline-blue-300"
                      >
                        <LogIn size={17} aria-hidden="true" />
                        {labels.signIn}
                      </button>
                    )}
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void reset()}
              aria-label={labels.newTrip}
              disabled={state.pending || submitting}
              className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-slate-700 hover:bg-blue-50 disabled:opacity-50"
            >
              <RotateCcw size={17} />
              <span className="hidden sm:inline">{labels.newTrip}</span>
            </button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-7xl px-4 pb-32 pt-8 sm:px-6 lg:pb-36 lg:pt-12">
        {authError && <p className="mb-5 rounded-xl bg-red-50 p-4 text-red-800" role="alert">{labels[authError]}</p>}
        {view === "admin" && auth.is_admin ? (
          <AdminUsersView
            users={adminUsers}
            loading={adminUsersLoading}
            hasMore={adminUsersHasMore}
            error={adminUsersError}
            usageAvailable={adminUsageAvailable}
            status={adminUsersStatus}
            updatingId={adminUserUpdatingId}
            selectedUserId={selectedAdminUserId}
            usage={adminUsage}
            usageLoading={adminUsageLoading}
            usageError={adminUsageError}
            usageStart={adminUsageStart}
            usageEnd={adminUsageEnd}
            onBack={() => setView("itinerary")}
            onLoadMore={() => void loadAdminUsers(true)}
            onChangeAccess={(user) => void changeAdminAccess(user)}
            onSelectUser={(id) => setSelectedAdminUserId((current) => current === id ? null : id)}
            onUsageStartChange={setAdminUsageStart}
            onUsageEndChange={setAdminUsageEnd}
            language={state.language}
          />
        ) : view === "graph" ? (
          <GraphView
            svg={graphSvg}
            imageLoading={graphImageLoading}
            imageUnavailable={graphImageUnavailable}
            fallbackLoading={graphFallbackLoading}
            error={graphError}
            onImageLoad={() => setGraphImageLoading(false)}
            onImageError={graphImageFailed}
            onBack={() => setView("itinerary")}
            language={state.language}
          />
        ) : view === "saved" && !auth?.authenticated ? (
          <section className="rise mx-auto mt-8 max-w-xl rounded-3xl border border-blue-100 bg-white p-6 shadow-sm sm:p-8" aria-labelledby="saved-auth-title">
            <button type="button" onClick={() => setView("itinerary")} className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 font-semibold text-slate-700 hover:bg-blue-100">
              <ArrowLeft size={18} aria-hidden="true" />{labels.back}
            </button>
            <h1 id="saved-auth-title" className="mt-5 font-heading text-2xl font-bold">{labels.savedTours}</h1>
            <p className="mt-3 leading-7 text-slate-700">{auth === null ? labels.authChecking : labels.authRequired}</p>
            {auth !== null && <button type="button" onClick={() => signIn("/?view=saved")} className="mt-5 inline-flex min-h-12 items-center rounded-xl bg-primary px-5 font-bold text-white hover:bg-blue-500">{labels.signIn}</button>}
          </section>
        ) : view === "saved" ? (
          <SavedToursView
            tours={savedTours}
            selectedTour={selectedSavedTour}
            loading={savedToursLoading}
            hasMore={savedToursHasMore}
            error={savedToursError}
            loadingId={savedTourLoadingId}
            deletingId={savedTourDeletingId}
            onBack={() => setView("itinerary")}
            onSelect={(id) => void selectSavedTour(id)}
            onDelete={(tour) => void deleteSavedTour(tour)}
            onLoadMore={() => void loadSavedTours(true)}
            onClaim={() => void claimOldTours()}
            claiming={claimingTours}
            claimStatus={claimStatus}
            language={state.language}
          />
        ) : (
          <>
            <section className="grid gap-8 lg:grid-cols-[1.05fr_.95fr] lg:items-center">
              <div>
                <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">
                  <ShieldCheck size={16} />
                  {labels.badge}
                </p>
                <h1 className="font-heading text-4xl font-bold tracking-tight sm:text-5xl">
                  {labels.heroTitle}
                  <br />
                  <span className="text-primary">{labels.heroAccent}</span>
                </h1>
                <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
                  {labels.heroDescription}
                </p>
              </div>
              <form
                noValidate
                onSubmit={makePlan}
                className="rounded-3xl bg-white p-5 shadow-xl shadow-blue-900/10 ring-1 ring-blue-100 sm:p-7"
              >
                <h2 className="font-heading text-xl font-bold">
                  {labels.startJourney}
                </h2>
                <div className="mt-5 grid gap-4">
                  <label className="font-semibold" htmlFor="destination">
                    {labels.destination}
                    <input
                      id="destination"
                      value={destination}
                      onChange={(event) => setDestination(event.target.value)}
                      aria-invalid={Boolean(errors.destination)}
                      aria-describedby={errors.destination ? "destination-error" : undefined}
                      placeholder={labels.destinationPlaceholder}
                      disabled={state.pending || submitting}
                      className="mt-2 block min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base"
                    />
                    <span id="destination-error"><FieldError message={errors.destination ? labels[errors.destination] : undefined} /></span>
                  </label>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="font-semibold">
                      <span id="start-date-label">{labels.startDate}</span>
                      <StartDatePicker
                        value={startDate}
                        language={state.language}
                        labels={{
                          startDate: labels.startDate,
                          previousMonth: labels.previousMonth,
                          nextMonth: labels.nextMonth,
                          closeCalendar: labels.closeCalendar,
                        }}
                        disabled={state.pending || submitting}
                        invalid={Boolean(errors.startDate)}
                        describedBy={
                          errors.startDate ? "start-date-error" : undefined
                        }
                        onChange={setStartDate}
                      />
                      <span id="start-date-error">
                        <FieldError
                          message={
                            errors.startDate ? labels[errors.startDate] : undefined
                          }
                        />
                      </span>
                    </div>
                    <label className="font-semibold" htmlFor="day-count">
                      {labels.days}
                      <select
                        id="day-count"
                        value={days}
                        onChange={(event) =>
                          setDays(Number(event.target.value))
                        }
                        aria-invalid={Boolean(errors.days)}
                        aria-describedby={errors.days ? "day-count-error" : undefined}
                        disabled={state.pending || submitting}
                        className="mt-2 block min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3"
                      >
                        {[1, 2, 3, 4, 5, 6, 7].map((number) => (
                          <option key={number} value={number}>
                            {number} {labels.dayUnit}
                          </option>
                        ))}
                      </select>
                      <span id="day-count-error"><FieldError message={errors.days ? labels[errors.days] : undefined} /></span>
                    </label>
                  </div>
                  <button
                    disabled={state.pending || submitting}
                    className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-primary px-5 font-bold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500 disabled:opacity-60"
                  >
                    {state.pending ? (
                      <LoaderCircle className="animate-spin" />
                    ) : (
                      <Sparkles size={18} />
                    )}
                    {labels.create}
                  </button>
                </div>
              </form>
            </section>
            {requestError && (
              <p
                className="mt-5 rounded-xl bg-red-50 p-4 text-red-800"
                role="alert"
              >
                {labels[requestError]}
              </p>
            )}
            {state.pending && (
              <section
                className="mt-7 flex items-center gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-blue-900"
                role="status"
                aria-live="polite"
              >
                <LoaderCircle className="animate-spin" />
                {labels.pending}
              </section>
            )}
            <TurnStatus response={state.response} />
            {state.plan ? (
              <>
                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-blue-100 bg-white p-4 shadow-sm">
                  <div>
                    <p className="font-semibold text-slate-900">{labels.saveTour}</p>
                    <p className="mt-1 text-sm text-slate-600">{labels.saveTourDescription}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void saveTour()}
                    disabled={state.pending || savingTour}
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 font-bold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingTour ? (
                      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Save className="size-4" aria-hidden="true" />
                    )}
                    {labels.saveTour}
                  </button>
                  {saveStatus && (
                    <p className="w-full text-sm text-slate-700" role="status" aria-live="polite">
                      {labels[saveStatus]}
                    </p>
                  )}
                </div>
                <PlanView
                  plan={state.plan}
                  visuals={visuals}
                  loading={visualsLoading}
                  language={state.language}
                />
              </>
            ) : (
              <section className="mt-8 rounded-3xl border border-dashed border-blue-200 bg-white/80 p-8 text-center text-slate-600">
                <Compass className="mx-auto mb-3 text-primary" />
                <h2 className="font-heading text-xl font-bold text-slate-900">
                  {labels.emptyTitle}
                </h2>
                <p className="mt-2">
                  {labels.emptyDescription}
                </p>
              </section>
            )}
          </>
        )}
      </main>
      {view !== "admin" && <ChatWidget
        open={chatOpen}
        onOpenChange={setChatOpen}
        state={state}
        message={message}
        setMessage={setMessage}
        errors={errors}
        setErrors={setErrors}
        submitting={submitting}
        requestError={requestError}
        onSend={(sent) => submit({ message: sent })}
        language={state.language}
      />}
      <footer className="mx-auto flex max-w-7xl flex-wrap gap-4 px-4 py-8 text-sm text-slate-500 sm:px-6">
        <span className="inline-flex items-center gap-1">
          <MapPin size={15} />
          {labels.currentTripSessionOnly}
        </span>
        <span className="inline-flex items-center gap-1">
          <CalendarDays size={15} />
          {labels.maxDays}
        </span>
        <span className="inline-flex items-center gap-1">
          <Plus size={15} />
          {labels.noFabrication}
        </span>
      </footer>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
