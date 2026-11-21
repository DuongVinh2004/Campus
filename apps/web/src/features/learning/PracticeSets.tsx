"use client";

import { useT, type MessageKey } from "@/lib/i18n";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { LearningGateway, type LearningMaterial } from "../../lib/data/api/learning-gateway";
import styles from "./learning.module.css";

const gateway = new LearningGateway();

interface Option { id: string; text: string }
interface Citation { page_no: number; quote: string }
interface StudentItem { id: string; kind: "single_choice" | "multi_choice" | "short_answer"; prompt: string; options: Option[] }
interface StaffItem extends StudentItem { answer: string[]; accepted: string[]; explanation: string; citations: Citation[]; revision: number }
interface SetRow { id: string; title: string; status: "DRAFT" | "PUBLISHED" | "RETIRED"; revision: number; item_count?: number; items?: (StudentItem | StaffItem)[] }
interface Result { correct: boolean; answer: string[]; accepted: string[]; explanation: string; citations: Citation[]; next_review_at: string }

const STATUS: Record<SetRow["status"], MessageKey> = { DRAFT: "psx.1", PUBLISHED: "psx.2", RETIRED: "psx.3" };

function message(error: unknown, t: (key: MessageKey) => string): string {
  return error instanceof Error && error.message ? error.message : t("psx.10");
}

function StudentSession({ set, onDone }: { set: SetRow; onDone: () => void }) {
  const t = useT();
  const [items, setItems] = useState<StudentItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [score, setScore] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    gateway.request<SetRow>(`/practice-sets/${set.id}/session`)
      .then((row) => { if (!cancelled) setItems((row.items ?? []) as StudentItem[]); })
      .catch((caught) => { if (!cancelled) setError(message(caught, t)); });
    return () => { cancelled = true; };
  }, [set.id]);

  if (error) return <p role="alert">{error}</p>;
  if (!items) return <p role="status">{t("psx.11")}</p>;
  if (items.length === 0) return <div><p>{t("psx.12")}</p><button type="button" onClick={onDone}>{t("psx.13")}</button></div>;
  if (index >= items.length) {
    return <div data-testid="practice-summary"><p>{t("psx.5", { n: items.length, s: score })}</p><button type="button" onClick={onDone}>{t("psx.13")}</button></div>;
  }
  const item = items[index];

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = item.kind === "short_answer" ? { text } : { choices: picked };
      const reply = await gateway.write<Result>(`/practice-items/${item.id}/attempts`, body);
      setResult(reply);
      setScore((value) => value + (reply.correct ? 1 : 0));
    } catch (caught) {
      setError(message(caught, t));
    } finally {
      setBusy(false);
    }
  }

  function next() {
    setResult(null);
    setPicked([]);
    setText("");
    setIndex((value) => value + 1);
  }

  const toggle = (id: string) => setPicked((current) => item.kind === "single_choice" ? [id] : current.includes(id) ? current.filter((x) => x !== id) : [...current, id]);
  const ready = item.kind === "short_answer" ? text.trim().length > 0 : picked.length > 0;
  return (
    <form onSubmit={(event) => void submit(event)} className={styles.stack} data-testid="practice-question">
      <p>{t("psx.6", { i: index + 1, n: items.length })}</p>
      <p><strong>{item.prompt}</strong></p>
      {item.kind === "short_answer" ? (
        <label>{t("psx.14")}<input value={text} disabled={!!result} maxLength={500} onChange={(event) => setText(event.target.value)} /></label>
      ) : (
        <fieldset disabled={!!result}>
          <legend>{item.kind === "single_choice" ? t("psx.15") : t("psx.16")}</legend>
          {item.options.map((option) => (
            <label key={option.id}>
              <input type={item.kind === "single_choice" ? "radio" : "checkbox"} name="choice" checked={picked.includes(option.id)} onChange={() => toggle(option.id)} />
              {option.text}
            </label>
          ))}
        </fieldset>
      )}
      {error && <p role="alert">{error}</p>}
      {!result ? <button type="submit" disabled={!ready || busy}>{t("psx.17")}</button> : (
        <div data-testid="practice-result">
          <p>{result.correct ? t("psx.18") : t("psx.19")}</p>
          {item.kind === "short_answer" ? <p>{t("psx.7", { a: result.accepted.join("; ") })}</p>
            : <p>{t("psx.8", { a: item.options.filter((o) => result.answer.includes(o.id)).map((o) => o.text).join("; ") })}</p>}
          {result.explanation && <p>{result.explanation}</p>}
          {result.citations.map((citation) => <blockquote key={`${citation.page_no}:${citation.quote}`}>Trang {citation.page_no}: {citation.quote}</blockquote>)}
          <button type="button" onClick={next}>{index + 1 < items.length ? t("psx.20") : t("psx.21")}</button>
        </div>
      )}
    </form>
  );
}

function NewItemForm({ set, onSaved }: { set: SetRow; onSaved: (revision: number) => void }) {
  const t = useT();
  const [kind, setKind] = useState<StudentItem["kind"]>("single_choice");
  const [prompt, setPrompt] = useState("");
  const [optionText, setOptionText] = useState("");
  const [answer, setAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [page, setPage] = useState("1");
  const [quote, setQuote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const lines = optionText.split("\n").map((line) => line.trim()).filter(Boolean);
      const options = kind === "short_answer" ? [] : lines.map((line, i) => ({ id: String.fromCharCode(97 + i), text: line }));
      const wanted = answer.split(",").map((part) => part.trim()).filter(Boolean);
      const body = {
        revision: set.revision, kind, prompt, options, explanation,
        answer: kind === "short_answer" ? [] : wanted.map((letter) => letter.toLowerCase()),
        accepted: kind === "short_answer" ? answer.split("|").map((part) => part.trim()).filter(Boolean) : [],
        citations: [{ page_no: Number(page), quote }],
      };
      const saved = await gateway.write<{ set_revision: number }>(`/practice-sets/${set.id}/items`, body, "PUT");
      setPrompt(""); setOptionText(""); setAnswer(""); setExplanation(""); setQuote("");
      onSaved(saved.set_revision);
    } catch (caught) {
      setError(message(caught, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={(event) => void save(event)} className={styles.stack} aria-label={t("psx.22")}>
      <label>{t("psx.23")}
        <select value={kind} onChange={(event) => setKind(event.target.value as StudentItem["kind"])}>
          <option value="single_choice">{t("psx.24")}</option><option value="multi_choice">{t("psx.25")}</option><option value="short_answer">{t("psx.26")}</option>
        </select>
      </label>
      <label>{t("psx.27")}<input value={prompt} maxLength={500} onChange={(event) => setPrompt(event.target.value)} required /></label>
      {kind !== "short_answer" && <label>{t("psx.28")}<textarea value={optionText} onChange={(event) => setOptionText(event.target.value)} required /></label>}
      <label>{kind === "short_answer" ? t("psx.29") : t("psx.30")}<input value={answer} onChange={(event) => setAnswer(event.target.value)} required /></label>
      <label>{t("psx.31")}<input value={explanation} maxLength={1000} onChange={(event) => setExplanation(event.target.value)} /></label>
      <label>{t("psx.32")}<input type="number" min={1} max={500} value={page} onChange={(event) => setPage(event.target.value)} required /></label>
      <label>{t("psx.33")}<textarea value={quote} onChange={(event) => setQuote(event.target.value)} minLength={12} required /></label>
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={busy}>{busy ? t("psx.34") : t("psx.22")}</button>
    </form>
  );
}

function StaffSet({ summary, onChanged }: { summary: SetRow; onChanged: () => void }) {
  const t = useT();
  const [set, setSet] = useState<SetRow>(summary);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try { setSet(await gateway.request<SetRow>(`/practice-sets/${summary.id}`)); setError(null); }
    catch (caught) { setError(message(caught, t)); }
  }, [summary.id]);
  useEffect(() => { void reload(); }, [reload]);

  async function publish() {
    setBusy(true);
    setError(null);
    try {
      await gateway.write(`/practice-sets/${set.id}/publication`, { revision: set.revision });
      await reload();
      onChanged();
    } catch (caught) {
      setError(message(caught, t));
    } finally {
      setBusy(false);
    }
  }

  const items = (set.items ?? []) as StaffItem[];
  return (
    <li data-testid={`practice-set-${set.id}`}>
      <p><strong>{set.title}</strong> · {t(STATUS[set.status])} · {t("psx.4", { n: items.length })}</p>
      <ol>{items.map((item) => <li key={item.id}>{item.prompt} <small>(trang {item.citations.map((c) => c.page_no).join(", ")})</small></li>)}</ol>
      {error && <p role="alert">{error}</p>}
      {set.status === "DRAFT" && (
        <>
          <NewItemForm set={set} onSaved={(revision) => { setSet((current) => ({ ...current, revision })); void reload(); }} />
          <button type="button" disabled={busy || items.length === 0} onClick={() => void publish()}>{t("psx.35")}</button>
        </>
      )}
    </li>
  );
}

export function SessionPracticeSets({ sessionId, materials, canManage, actorId }: { sessionId: string; materials: LearningMaterial[]; canManage: boolean; actorId: string }) {
  const t = useT();
  const [sets, setSets] = useState<SetRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [versionId, setVersionId] = useState("");
  const [active, setActive] = useState<SetRow | null>(null);
  const versions = materials.filter((m) => m.visibility === "VISIBLE" && m.current_published_version_id).map((m) => ({ id: m.current_published_version_id as string, title: m.title }));

  const load = useCallback(async () => {
    try { setSets(await gateway.list<SetRow>(`/sessions/${sessionId}/practice-sets`)); setError(null); }
    catch (caught) { setError(message(caught, t)); }
  }, [sessionId]);
  useEffect(() => { void load(); }, [load, actorId]);

  async function create(event: FormEvent) {
    event.preventDefault();
    try {
      await gateway.write(`/sessions/${sessionId}/practice-sets`, { version_id: versionId || versions[0]?.id, title });
      setTitle("");
      await load();
    } catch (caught) { setError(message(caught, t)); }
  }

  if (active) return <section aria-label={t("psx.36")}><StudentSession set={active} onDone={() => setActive(null)} /></section>;
  return (
    <section aria-labelledby={`practice-${sessionId}`} className={styles.stack} data-testid="practice-sets">
      <h3 id={`practice-${sessionId}`}>{t("psx.37")}</h3>
      {error && <p role="alert">{error}</p>}
      {!sets ? <p role="status">{t("psx.38")}</p> : sets.length === 0 ? <p>{t("psx.39")}</p> : canManage ? (
        <ul>{sets.map((row) => <StaffSet key={row.id} summary={row} onChanged={() => void load()} />)}</ul>
      ) : (
        <ul>{sets.map((row) => <li key={row.id}>{row.title} · {t("psx.9", { n: row.item_count ?? 0 })} <button type="button" onClick={() => setActive(row)}>{t("psx.36")}</button></li>)}</ul>
      )}
      {canManage && (
        <form onSubmit={(event) => void create(event)} aria-label={t("psx.40")}>
          <label>{t("psx.41")}<input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} required /></label>
          <label>{t("psx.42")}
            <select value={versionId} onChange={(event) => setVersionId(event.target.value)}>
              {versions.map((version) => <option key={version.id} value={version.id}>{version.title}</option>)}
            </select>
          </label>
          <button type="submit" disabled={versions.length === 0}>{t("psx.40")}</button>
        </form>
      )}
    </section>
  );
}
