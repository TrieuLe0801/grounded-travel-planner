import { createRoot } from "react-dom/client";
import {
  type Dispatch,
  type FormEvent,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ArrowLeft,
  Bot,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Compass,
  ExternalLink,
  ImageOff,
  LoaderCircle,
  MapPin,
  MessageCircle,
  Network,
  Plus,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import "./index.css";

type Source = { title: string; url: string };
type Visual = {
  image_url: string;
  image_page_url: string;
  image_alt: string;
  image_credit: string;
  image_license: string;
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
type ApiState = {
  plan: Plan | null;
  pending: boolean;
  response: TurnResponse | null;
  visuals_by_entry?: Record<string, Visual>;
};
type View = "itinerary" | "graph";
const today = (() => {
  const date = new Date();
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
})();

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
    throw new Error(body?.detail || "Không thể kết nối máy chủ.");
  }
  return response.json() as Promise<T>;
}
function FieldError({ message }: { message?: string }) {
  return message ? (
    <p className="mt-1 text-sm font-medium text-red-700">{message}</p>
  ) : null;
}
function Photo({ visual, placeName }: { visual?: Visual; placeName: string }) {
  if (!visual)
    return (
      <div className="flex aspect-[16/9] items-center justify-center rounded-2xl bg-slate-100 px-4 text-center text-sm text-slate-500">
        <ImageOff className="mr-2 size-4" />
        Chưa tìm được ảnh có giấy phép cho {placeName}.
      </div>
    );
  return (
    <figure>
      <a
        href={visual.image_page_url}
        target="_blank"
        rel="noreferrer"
        className="block overflow-hidden rounded-2xl focus-visible:outline focus-visible:outline-4 focus-visible:outline-cyan-300"
      >
        <img
          src={visual.image_url}
          alt={visual.image_alt}
          className="aspect-[16/9] w-full object-cover"
          loading="lazy"
        />
      </a>
      <figcaption className="mt-2 text-xs leading-5 text-slate-500">
        Ảnh: {visual.image_credit} · {visual.image_license} ·{" "}
        <a
          href={visual.image_page_url}
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-sea hover:underline"
        >
          nguồn ảnh
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
}: {
  plan: Plan;
  visuals: Record<string, Visual>;
  loading: boolean;
}) {
  const days = Array.from({ length: plan.day_count }, (_, index) => index + 1);
  return (
    <section aria-labelledby="itinerary-title" className="rise mt-8">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-coral">
            Lịch trình đã kiểm tra
          </p>
          <h2 id="itinerary-title" className="font-heading text-2xl font-bold">
            {plan.destination}{" "}
            <span className="text-slate-400">· v{plan.revision}</span>
          </h2>
        </div>
        <p className="text-sm text-slate-600">
          {plan.start_date} · {plan.day_count} ngày
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
          Đang tìm ảnh có giấy phép…
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
              className="rounded-3xl border border-orange-100 bg-white p-5 shadow-sm"
              key={day}
            >
              <h3 className="font-heading text-lg font-bold">Ngày {day}</h3>
              <div className="mt-4 space-y-6">
                {entries.length ? (
                  entries.map((entry, index) => (
                    <article
                      className="border-l-2 border-cyan-500 pl-4"
                      key={entry.id}
                    >
                      <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-cyan-800">
                        <Clock3 size={16} />
                        {entry.start_time.slice(0, 5)}–
                        {entry.end_time.slice(0, 5)}{" "}
                        <span className="text-slate-400">·</span> Điểm{" "}
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
                        />
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
                        <span className="rounded-full bg-orange-100 px-3 py-1 text-orange-800">
                          Tham quan ước tính ~
                          {entry.place.visit_minutes_estimate} phút
                        </span>
                        <span className="rounded-full bg-cyan-50 px-3 py-1 text-cyan-800">
                          Di chuyển ước tính ~
                          {entry.place.travel_minutes_estimate} phút
                        </span>
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
                          Giờ mở cửa:{" "}
                          {entry.place.opening_hours_verified
                            ? entry.place.opening_hours
                            : "chưa xác minh"}
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
                            className="inline-flex items-center gap-1 font-semibold text-sea underline-offset-4 hover:underline"
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
                    Chưa có điểm nào trong ngày này.
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
}: {
  svg: string;
  imageLoading: boolean;
  imageUnavailable: boolean;
  fallbackLoading: boolean;
  error: string;
  onImageLoad: () => void;
  onImageError: () => void;
  onBack: () => void;
}) {
  return (
    <section aria-labelledby="graph-title" className="rise mt-8">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 font-semibold text-slate-700 hover:bg-orange-100"
      >
        <ArrowLeft size={18} />
        Về lịch trình
      </button>
      <div className="mt-4 rounded-3xl border border-orange-100 bg-white p-5 shadow-sm sm:p-7">
        <p className="inline-flex items-center gap-2 rounded-full bg-cyan-50 px-3 py-1 text-sm font-semibold text-cyan-800">
          <Network size={16} />
          Chỉ đọc
        </p>
        <h1 id="graph-title" className="mt-4 font-heading text-2xl font-bold">
          Kiến trúc LangGraph
        </h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          Sơ đồ lấy từ workflow đã biên dịch. Việc xem trang này không tạo hoặc
          thay đổi lịch trình.
        </p>
        {!imageUnavailable && (
          <figure
            className="mt-6 min-h-72 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-3 sm:p-6"
            aria-busy={imageLoading}
          >
            {imageLoading && (
              <p className="flex items-center gap-2 text-slate-600" role="status">
                <LoaderCircle className="animate-spin" />
                Đang tải ảnh kiến trúc…
              </p>
            )}
            <img
              src="/api/graph/image"
              alt="Sơ đồ workflow LangGraph gồm Coordinator, Planner, Chat và các bước kiểm tra"
              className="graph-image mx-auto max-h-[70dvh] max-w-full object-contain"
              decoding="async"
              onLoad={onImageLoad}
              onError={onImageError}
            />
            <figcaption className="mt-3 text-sm text-slate-600">
              Ảnh PNG được tạo trực tiếp từ workflow LangGraph đã biên dịch.
            </figcaption>
          </figure>
        )}
        {imageUnavailable && (
          <>
            <p
              className="mt-6 rounded-xl bg-amber-50 p-4 text-amber-900"
              role="status"
            >
              Không thể tạo ảnh PNG lúc này; đang dùng sơ đồ SVG dự phòng.
            </p>
            {fallbackLoading && (
              <p className="mt-6 flex items-center gap-2 text-slate-600" role="status">
                <LoaderCircle className="animate-spin" />
                Đang tải sơ đồ dự phòng…
              </p>
            )}
            {error && (
              <p
                className="mt-6 rounded-xl bg-red-50 p-4 text-red-800"
                role="alert"
              >
                {error}
              </p>
            )}
            {svg && (
              <div
                className="graph-svg mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50 p-3 sm:p-6"
                role="img"
                aria-label="Sơ đồ workflow LangGraph gồm Coordinator, Planner, Chat và các bước kiểm tra"
                dangerouslySetInnerHTML={{ __html: svg }}
              />
            )}
          </>
        )}
      </div>
    </section>
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
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  state: ApiState;
  message: string;
  setMessage: Dispatch<SetStateAction<string>>;
  errors: Record<string, string>;
  setErrors: Dispatch<SetStateAction<Record<string, string>>>;
  submitting: boolean;
  requestError: string;
  onSend: (message: string) => Promise<boolean>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

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
        chat: "Hãy nhập yêu cầu trước khi gửi.",
      }));
      return;
    }
    setErrors((current) => ({ ...current, chat: "" }));
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
          className="chat-panel fixed bottom-24 right-4 z-40 flex h-[min(620px,calc(100dvh-7rem))] w-[calc(100vw-2rem)] max-w-md flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl shadow-slate-950/20 sm:right-6"
          role="dialog"
          aria-labelledby="chat-panel-title"
        >
          <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-ink px-4 py-4 text-white sm:px-5">
            <div className="flex min-w-0 items-center gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-cyan-500">
                <Bot aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h2 id="chat-panel-title" className="font-heading font-bold">
                  Trợ lý hành trình
                </h2>
                <p className="truncate text-sm text-slate-300">
                  Điều chỉnh lịch trình bằng chat
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-xl text-slate-200 transition hover:bg-white/10 hover:text-white"
              aria-label="Đóng cửa sổ chat"
              title="Đóng chat"
            >
              <X size={20} aria-hidden="true" />
            </button>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-5">
            {!state.response ? (
              <div className="rounded-2xl bg-orange-50 p-4 text-sm text-slate-700">
                <p className="font-semibold text-ink">Bạn muốn đổi gì?</p>
                <p className="mt-1 leading-6">
                  Gửi yêu cầu tự nhiên để thêm, xoá, đổi giờ hoặc kéo dài chuyến
                  đi. Lịch chỉ được cập nhật sau khi kiểm tra nguồn và thời gian.
                </p>
                <div className="mt-4 grid gap-2">
                  {[
                    "Thêm Lô Lô Chải vào ngày 2",
                    "Chuyển điểm 1 sang 11:00 ngày 1",
                    "Thêm một ngày cho chuyến đi",
                  ].map((example) => (
                    <button
                      type="button"
                      key={example}
                      onClick={() => setMessage(example)}
                      className="min-h-11 rounded-xl border border-orange-200 bg-white px-3 text-left text-sm font-semibold text-slate-700 transition hover:border-coral hover:bg-orange-50"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                <p className="mb-3 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
                  Phản hồi gần nhất
                </p>
                <TurnStatus response={state.response} className="mt-0" />
              </>
            )}
            {state.pending && (
              <p
                className="mt-4 flex items-center gap-2 rounded-xl bg-cyan-50 p-3 text-sm font-semibold text-cyan-950"
                role="status"
                aria-live="polite"
              >
                <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                Đang kiểm tra yêu cầu…
              </p>
            )}
            {requestError && (
              <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-800" role="alert">
                {requestError}
              </p>
            )}
          </div>

          <form
            className="border-t border-slate-200 bg-slate-50 p-3 sm:p-4"
            onSubmit={submitChat}
          >
            <label className="sr-only" htmlFor="chat-widget-input">
              Yêu cầu thay đổi lịch trình
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
                  className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base text-ink placeholder:text-slate-400"
                  placeholder="Ví dụ: thêm một ngày…"
                />
                <span id="chat-widget-error">
                  <FieldError message={errors.chat} />
                </span>
              </div>
              <button
                type="submit"
                disabled={state.pending || submitting || !message.trim()}
                className="inline-flex min-h-12 min-w-12 items-center justify-center rounded-xl bg-coral px-4 font-bold text-white transition hover:bg-orange-700 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Gửi yêu cầu chat"
                title="Gửi yêu cầu"
              >
                {submitting || state.pending ? (
                  <LoaderCircle className="animate-spin" aria-hidden="true" />
                ) : (
                  <Send size={19} aria-hidden="true" />
                )}
                <span className="sr-only">Gửi</span>
              </button>
            </div>
          </form>
        </section>
      )}

      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className="fixed bottom-4 right-4 z-40 inline-flex min-h-14 min-w-14 items-center justify-center rounded-full bg-coral text-white shadow-xl shadow-orange-950/25 transition hover:-translate-y-0.5 hover:bg-orange-700 focus-visible:ring-4 focus-visible:ring-cyan-200 sm:bottom-6 sm:right-6"
        aria-expanded={open}
        aria-controls="chat-panel"
        aria-label={open ? "Đóng cửa sổ chat" : "Mở cửa sổ chat"}
        title={open ? "Đóng chat" : "Mở chat"}
      >
        {open ? <X aria-hidden="true" /> : <MessageCircle aria-hidden="true" />}
        <span className="sr-only">{open ? "Đóng chat" : "Mở chat"}</span>
      </button>
    </>
  );
}

function App() {
  const [state, setState] = useState<ApiState>({
    plan: null,
    pending: false,
    response: null,
  });
  const [destination, setDestination] = useState("");
  const [startDate, setStartDate] = useState(today);
  const [days, setDays] = useState(2);
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [requestError, setRequestError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [visuals, setVisuals] = useState<Record<string, Visual>>({});
  const [visualsLoading, setVisualsLoading] = useState(false);
  const [view, setView] = useState<View>("itinerary");
  const [chatOpen, setChatOpen] = useState(false);
  const [graphSvg, setGraphSvg] = useState("");
  const [graphImageLoading, setGraphImageLoading] = useState(true);
  const [graphImageUnavailable, setGraphImageUnavailable] = useState(false);
  const [graphFallbackLoading, setGraphFallbackLoading] = useState(false);
  const [graphError, setGraphError] = useState("");
  const load = async () => {
    try {
      setState(await api<ApiState>("/api/session"));
    } catch {
      await api<ApiState>("/api/session", { method: "POST" });
      setState(await api<ApiState>("/api/session"));
    }
  };
  useEffect(() => {
    void load().catch((error: unknown) =>
      setRequestError(
        error instanceof Error ? error.message : "Không thể bắt đầu phiên.",
      ),
    );
  }, []);
  useEffect(() => {
    if (!state.pending) return;
    const timer = window.setInterval(() => void load(), 1200);
    return () => window.clearInterval(timer);
  }, [state.pending]);
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
      .catch((error: unknown) =>
        setGraphError(
          error instanceof Error ? error.message : "Không thể tải sơ đồ.",
        ),
      )
      .finally(() => setGraphFallbackLoading(false));
  }, [graphFallbackLoading, graphImageUnavailable, graphSvg]);
  const submit = async (body: object) => {
    setRequestError("");
    setSubmitting(true);
    try {
      await api<{ accepted: boolean }>("/api/turns", {
        method: "POST",
        body: JSON.stringify(body),
      });
      await load();
      return true;
    } catch (error) {
      setRequestError(
        error instanceof Error ? error.message : "Không thể gửi yêu cầu.",
      );
      return false;
    } finally {
      setSubmitting(false);
    }
  };
  const makePlan = (event: FormEvent) => {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!destination.trim())
      next.destination = "Hãy nhập điểm đến hoặc địa danh.";
    if (!startDate) next.startDate = "Hãy chọn ngày bắt đầu cụ thể.";
    if (!Number.isInteger(days) || days < 1 || days > 7)
      next.days = "Số ngày phải từ 1 đến 7.";
    setErrors(next);
    if (Object.keys(next).length) return;
    void submit({
      message: `Hãy tạo lịch trình tham quan ${days} ngày tại ${destination.trim()}, bắt đầu ngày ${startDate}.`,
      request: {
        destination: destination.trim(),
        start_date: startDate,
        day_count: days,
      },
    });
  };
  const openGraph = () => setView("graph");
  const graphImageFailed = () => {
    setGraphImageLoading(false);
    setGraphImageUnavailable(true);
  };
  const reset = async () => {
    if (state.plan && !window.confirm("Tạo chuyến đi mới và bỏ lịch trình hiện tại?")) return;
    setRequestError("");
    try {
      await api<ApiState>("/api/session/reset", { method: "POST" });
      setMessage("");
      setVisuals({});
      await load();
    } catch (error) {
      setRequestError(
        error instanceof Error ? error.message : "Không thể tạo chuyến đi mới.",
      );
    }
  };
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 rounded bg-white p-3"
      >
        Đi tới nội dung
      </a>
      <header className="border-b border-orange-100 bg-white/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <a
            className="flex items-center gap-3 font-heading font-bold"
            href="/"
          >
            <span className="grid size-10 place-items-center rounded-2xl bg-coral text-white">
              <Compass />
            </span>
            <span>Hành trình có căn cứ</span>
          </a>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={openGraph}
              aria-label="Xem kiến trúc LangGraph"
              className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-slate-700 hover:bg-orange-50"
            >
              <Network size={17} />
              <span className="hidden sm:inline">Xem graph</span>
            </button>
            <button
              type="button"
              onClick={() => void reset()}
              aria-label="Tạo chuyến đi mới"
              disabled={state.pending || submitting}
              className="inline-flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-slate-700 hover:bg-orange-50 disabled:opacity-50"
            >
              <RotateCcw size={17} />
              <span className="hidden sm:inline">Chuyến đi mới</span>
            </button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-7xl px-4 pb-32 pt-8 sm:px-6 lg:pb-36 lg:pt-12">
        {view === "graph" ? (
          <GraphView
            svg={graphSvg}
            imageLoading={graphImageLoading}
            imageUnavailable={graphImageUnavailable}
            fallbackLoading={graphFallbackLoading}
            error={graphError}
            onImageLoad={() => setGraphImageLoading(false)}
            onImageError={graphImageFailed}
            onBack={() => setView("itinerary")}
          />
        ) : (
          <>
            <section className="grid gap-8 lg:grid-cols-[1.05fr_.95fr] lg:items-center">
              <div>
                <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-cyan-50 px-3 py-1 text-sm font-semibold text-cyan-800">
                  <ShieldCheck size={16} />
                  Nguồn thật · kiểm tra lịch trước khi lưu
                </p>
                <h1 className="font-heading text-4xl font-bold tracking-tight sm:text-5xl">
                  Chọn điểm đến.
                  <br />
                  <span className="text-coral">Đi đúng nhịp của bạn.</span>
                </h1>
                <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
                  Tạo lịch tham quan có nguồn tham khảo, rồi trò chuyện để đổi
                  ngày, giờ hoặc địa điểm. Thời lượng và thông tin chưa xác minh
                  luôn được gắn nhãn rõ.
                </p>
              </div>
              <form
                noValidate
                onSubmit={makePlan}
                className="rounded-3xl bg-white p-5 shadow-xl shadow-orange-950/5 ring-1 ring-orange-100 sm:p-7"
              >
                <h2 className="font-heading text-xl font-bold">
                  Bắt đầu hành trình
                </h2>
                <div className="mt-5 grid gap-4">
                  <label className="font-semibold" htmlFor="destination">
                    Điểm đến
                    <input
                      id="destination"
                      value={destination}
                      onChange={(event) => setDestination(event.target.value)}
                      aria-invalid={Boolean(errors.destination)}
                      aria-describedby={errors.destination ? "destination-error" : undefined}
                      placeholder="Ví dụ: Huế"
                      disabled={state.pending || submitting}
                      className="mt-2 block min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-base"
                    />
                    <span id="destination-error"><FieldError message={errors.destination} /></span>
                  </label>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <label className="font-semibold" htmlFor="start-date">
                      Ngày bắt đầu
                      <input
                        id="start-date"
                        type="date"
                        value={startDate}
                        onChange={(event) => setStartDate(event.target.value)}
                        aria-invalid={Boolean(errors.startDate)}
                        aria-describedby={errors.startDate ? "start-date-error" : undefined}
                        disabled={state.pending || submitting}
                        className="mt-2 block min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3"
                      />
                      <span id="start-date-error"><FieldError message={errors.startDate} /></span>
                    </label>
                    <label className="font-semibold" htmlFor="day-count">
                      Số ngày
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
                            {number} ngày
                          </option>
                        ))}
                      </select>
                      <span id="day-count-error"><FieldError message={errors.days} /></span>
                    </label>
                  </div>
                  <button
                    disabled={state.pending || submitting}
                    className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-coral px-5 font-bold text-white shadow-lg shadow-orange-500/20 hover:bg-orange-700 disabled:opacity-60"
                  >
                    {state.pending ? (
                      <LoaderCircle className="animate-spin" />
                    ) : (
                      <Sparkles size={18} />
                    )}
                    Tạo lịch trình
                  </button>
                </div>
              </form>
            </section>
            {requestError && (
              <p
                className="mt-5 rounded-xl bg-red-50 p-4 text-red-800"
                role="alert"
              >
                {requestError}
              </p>
            )}
            {state.pending && (
              <section
                className="mt-7 flex items-center gap-3 rounded-2xl border border-cyan-200 bg-cyan-50 p-4 text-cyan-950"
                role="status"
                aria-live="polite"
              >
                <LoaderCircle className="animate-spin" />
                Coordinator đang phân phối yêu cầu cho Planner và Chat. Bạn có
                thể tiếp tục xem lịch hiện tại hoặc xem graph.
              </section>
            )}
            <TurnStatus response={state.response} />
            {state.plan ? (
              <PlanView
                plan={state.plan}
                visuals={visuals}
                loading={visualsLoading}
              />
            ) : (
              <section className="mt-8 rounded-3xl border border-dashed border-orange-200 bg-white/70 p-8 text-center text-slate-600">
                <Compass className="mx-auto mb-3 text-coral" />
                <h2 className="font-heading text-xl font-bold text-ink">
                  Lịch trình của bạn sẽ xuất hiện ở đây
                </h2>
                <p className="mt-2">
                  Chọn điểm đến, ngày bắt đầu và số ngày để bắt đầu.
                </p>
              </section>
            )}
          </>
        )}
      </main>
      <ChatWidget
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
      />
      <footer className="mx-auto flex max-w-7xl flex-wrap gap-4 px-4 py-8 text-sm text-slate-500 sm:px-6">
        <span className="inline-flex items-center gap-1">
          <MapPin size={15} />
          Chỉ lưu trong phiên duyệt web
        </span>
        <span className="inline-flex items-center gap-1">
          <CalendarDays size={15} />
          Tối đa 7 ngày
        </span>
        <span className="inline-flex items-center gap-1">
          <Plus size={15} />
          Không tự tạo nguồn hoặc giờ mở cửa
        </span>
      </footer>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
