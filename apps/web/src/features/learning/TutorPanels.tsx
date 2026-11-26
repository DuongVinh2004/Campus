"use client";

import { useT, type MessageKey } from "@/lib/i18n";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { LearningGateway } from "../../lib/data/api/learning-gateway";
import styles from "./learning.module.css";

const gateway = new LearningGateway();

export interface TutorState { hint_available: boolean; wrong_attempts: number; solution_after: number }
interface Hint { level: 1 | 2 | 3; hint: string; quote: string; page: number; origin: "MODEL" | "TEMPLATE"; remaining_today: number; turns_left: number; solution_after: number }
type Band = "MASTERED" | "PROGRESSING" | "NEEDS_REVIEW" | "NOT_ENOUGH_DATA";
interface MyMasteryRow { concept_id: string; label: string; p_known: number; attempts: number; band: Band }
interface MyMasteryView { concepts: MyMasteryRow[]; review_first: { concept_id: string; label: string } | null }
type Cell = number | string;
interface MapConcept { concept_id: string; label: string; students: Cell; bands: Record<Band, Cell> | null; needs_review_rate: number | null }
interface MapItem { item_id: string; prompt: string; attempts: Cell; first_try_rate: number | null }
interface MapView { suppressed: boolean; students: Cell; concepts: MapConcept[]; items: MapItem[] }
interface Concept { id: string; label: string; description: string; status: "PROPOSED" | "APPROVED" | "RETIRED"; revision: number; links?: { kind: string; target: string }[] }
interface Settings { tutor_enabled: boolean; reveal_after_attempts: number; model_hints_enabled: boolean; revision: number }

const BANDS: Record<Band, MessageKey> = { MASTERED: "tut.15", PROGRESSING: "tut.16", NEEDS_REVIEW: "tut.17", NOT_ENOUGH_DATA: "tut.18" };
const CONCEPT_STATUS: Record<Concept["status"], MessageKey> = { APPROVED: "tut.47", PROPOSED: "tut.48", RETIRED: "tut.49" };

function problem(error: unknown, t: (key: MessageKey, values?: Record<string, string | number>) => string, solutionAfter?: number): string {
  // The gateway's errors carry the server's code (LearningApiError); read it by shape so any error object works.
  const code = error && typeof error === "object" && "code" in error ? String((error as { code: unknown }).code) : "";
  if (code === "HINT_LEVEL_NOT_ALLOWED" && solutionAfter) return t("tut.5", { n: solutionAfter });
  if (code === "HINT_TURNS_EXHAUSTED") return t("tut.50");
  if (code === "TUTOR_DISABLED_FOR_OFFERING") return t("tut.51");
  return error instanceof Error && error.message ? error.message : t("tut.45");
}

/** Shown under a wrong answer while the class uses the tutor: hints first, the solution only from the lecturer's threshold. */
export function TutorBox({ itemId, tutor, onRetry }: { itemId: string; tutor: TutorState; onRetry: () => void }) {
  const t = useT();
  const [hints, setHints] = useState<Hint[]>([]);
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const solutionOpen = tutor.wrong_attempts >= tutor.solution_after;

  async function ask(body: { more?: boolean; solution?: boolean; reply?: string }) {
    setBusy(true);
    setError(null);
    try {
      const given = await gateway.write<Hint>(`/tutor/practice-items/${itemId}/hints`, body);
      setHints((current) => [...current, given]);
      setReply("");
    } catch (caught) {
      setError(problem(caught, t, tutor.solution_after));
    } finally {
      setBusy(false);
    }
  }

  const last = hints[hints.length - 1];
  return (
    <section aria-label={t("tut.1")} className={styles.stack} data-testid="tutor-box">
      <p>{t("tut.12")}</p>
      <ol aria-live="polite">
        {hints.map((h, i) => (
          <li key={i}>
            <p>{h.hint}</p>
            {h.quote && <blockquote>{t("tut.11", { p: h.page })}: «{h.quote}»</blockquote>}
            <small>{h.origin === "MODEL" ? t("tut.9") : t("tut.10")}</small>
          </li>
        ))}
      </ol>
      {last && last.turns_left >= 0 && <p><small>{t("tut.13", { n: last.turns_left })}</small></p>}
      {error && <p role="alert">{error}</p>}
      <div className={styles.row}>
        {hints.length === 0
          ? <button type="button" disabled={busy} onClick={() => void ask({})}>{t("tut.2")}</button>
          : <button type="button" disabled={busy || (last?.level ?? 0) >= 2} onClick={() => void ask({ more: true })}>{t("tut.3")}</button>}
        <button type="button" disabled={busy || !solutionOpen} aria-describedby={`solution-note-${itemId}`} onClick={() => void ask({ solution: true })}>{t("tut.4")}</button>
        <button type="button" onClick={onRetry}>{t("tut.6")}</button>
      </div>
      {!solutionOpen && <p id={`solution-note-${itemId}`}><small>{t("tut.5", { n: tutor.solution_after })}</small></p>}
      {hints.length > 0 && last.level < 3 && (
        <form onSubmit={(event: FormEvent) => { event.preventDefault(); if (reply.trim()) void ask({ reply: reply.trim() }); }}>
          <label>{t("tut.7")}<textarea value={reply} maxLength={500} onChange={(event) => setReply(event.target.value)} /></label>
          <button type="submit" disabled={busy || !reply.trim()}>{t("tut.8")}</button>
        </form>
      )}
    </section>
  );
}

/** A student's own estimated mastery per concept. Renders nothing when the feature is off for this deployment. */
export function MyMastery({ offeringId }: { offeringId: string }) {
  const t = useT();
  const [view, setView] = useState<MyMasteryView | null | "off">(null);
  useEffect(() => {
    let alive = true;
    gateway.request<MyMasteryView>(`/mastery/offerings/${offeringId}/me`)
      .then((value) => { if (alive) setView(value); })
      .catch(() => { if (alive) setView("off"); });
    return () => { alive = false; };
  }, [offeringId]);
  if (view === "off" || view === null) return null;
  return (
    <section aria-labelledby={`mastery-${offeringId}`} className={styles.stack} data-testid="my-mastery">
      <h3 id={`mastery-${offeringId}`}>{t("tut.14")}</h3>
      {view.concepts.length === 0 ? <p>{t("tut.21")}</p> : (
        <>
          {view.review_first && <p><strong>{t("tut.19", { c: view.review_first.label })}</strong></p>}
          <ul>
            {view.concepts.map((row) => (
              <li key={row.concept_id}>
                {row.label}: {t(BANDS[row.band])}{" "}
                <meter min={0} max={1} value={row.p_known} aria-label={`${row.label}: ${t(BANDS[row.band])}`} />
              </li>
            ))}
          </ul>
          <p><small>{t("tut.20")}</small></p>
        </>
      )}
    </section>
  );
}

function TutorSettingsForm({ offeringId }: { offeringId: string }) {
  const t = useT();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setSettings(await gateway.request<Settings>(`/tutor/offerings/${offeringId}/settings`)); } catch { setSettings(null); }
  }, [offeringId]);
  useEffect(() => { void load(); }, [load]);
  if (!settings) return null;
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    try {
      setSettings(await gateway.write<Settings>(`/tutor/offerings/${offeringId}/settings`, settings, "PUT"));
      setNote(t("tut.43"));
    } catch (caught) { setNote(problem(caught, t)); await load(); }
  }
  return (
    <form onSubmit={(event) => void save(event)} aria-label={t("tut.38")} className={styles.stack}>
      <h4>{t("tut.38")}</h4>
      <label><input type="checkbox" checked={settings.tutor_enabled} onChange={(e) => setSettings({ ...settings, tutor_enabled: e.target.checked })} /> {t("tut.39")}</label>
      <label>{t("tut.40")}
        <input type="number" min={1} max={5} value={settings.reveal_after_attempts}
          onChange={(e) => setSettings({ ...settings, reveal_after_attempts: Math.min(5, Math.max(1, Number(e.target.value) || 1)) })} />
      </label>
      <label><input type="checkbox" checked={settings.model_hints_enabled} onChange={(e) => setSettings({ ...settings, model_hints_enabled: e.target.checked })} /> {t("tut.41")}</label>
      <button type="submit">{t("tut.42")}</button>
      {note && <p role="status">{note}</p>}
    </form>
  );
}

function ConceptManager({ offeringId, onChanged }: { offeringId: string; onChanged: () => void }) {
  const t = useT();
  const [concepts, setConcepts] = useState<Concept[] | null>(null);
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [pages, setPages] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setConcepts((await gateway.request<{ concepts: Concept[] }>(`/mastery/offerings/${offeringId}/concepts`)).concepts); setError(null); }
    catch (caught) { setError(problem(caught, t)); }
  }, [offeringId]);
  useEffect(() => { void load(); }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    const links = pages.split(",").map((part) => part.trim()).filter(Boolean).map((target) => ({ kind: "PAGE", target }));
    try {
      await gateway.write(`/mastery/offerings/${offeringId}/concepts`, { label, description, links });
      setLabel(""); setDescription(""); setPages("");
      await load(); onChanged();
    } catch (caught) { setError(problem(caught, t)); }
  }
  async function change(concept: Concept, status: "APPROVED" | "RETIRED") {
    try { await gateway.write(`/mastery/concepts/${concept.id}`, { revision: concept.revision, status }, "PATCH"); await load(); onChanged(); }
    catch (caught) { setError(problem(caught, t)); }
  }
  return (
    <section aria-label={t("tut.31")} className={styles.stack}>
      <h4>{t("tut.31")}</h4>
      {error && <p role="alert">{error}</p>}
      {!concepts ? <p role="status">{t("tut.44")}</p> : (
        <ul>
          {concepts.map((c) => (
            <li key={c.id}>
              <strong>{c.label}</strong> · {t(CONCEPT_STATUS[c.status])}
              {c.status === "PROPOSED" && <button type="button" onClick={() => void change(c, "APPROVED")}>{t("tut.37")}</button>}
              {c.status !== "RETIRED" && <button type="button" onClick={() => void change(c, "RETIRED")}>{t("tut.36")}</button>}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={(event) => void create(event)} aria-label={t("tut.35")}>
        <label>{t("tut.32")}<input value={label} minLength={2} maxLength={120} onChange={(e) => setLabel(e.target.value)} required /></label>
        <label>{t("tut.33")}<input value={description} maxLength={600} onChange={(e) => setDescription(e.target.value)} /></label>
        <label>{t("tut.34")}<input value={pages} onChange={(e) => setPages(e.target.value)} /></label>
        <button type="submit">{t("tut.35")}</button>
      </form>
    </section>
  );
}

function cell(value: Cell): string {
  return typeof value === "number" ? String(value) : value.replace("<", "< ");
}

/** The lecturer's view: tutor settings, concepts and the class map (counts only; groups under 5 show "< 5"). */
export function ClassMastery({ offeringId }: { offeringId: string }) {
  const t = useT();
  const [map, setMap] = useState<MapView | null | "off">(null);
  const load = useCallback(async () => {
    try { setMap(await gateway.request<MapView>(`/mastery/offerings/${offeringId}/map`)); } catch { setMap("off"); }
  }, [offeringId]);
  useEffect(() => { void load(); }, [load]);
  return (
    <section aria-labelledby={`class-mastery-${offeringId}`} className={styles.stack} data-testid="class-mastery">
      <h3 id={`class-mastery-${offeringId}`}>{t("tut.22")}</h3>
      <TutorSettingsForm offeringId={offeringId} />
      {map !== "off" && <ConceptManager offeringId={offeringId} onChanged={() => void load()} />}
      {map === null ? <p role="status">{t("tut.44")}</p> : map === "off" ? null : map.suppressed ? <p>{t("tut.23")}</p> : (
        <>
          <table>
            <caption>{t("tut.22")}</caption>
            <thead><tr><th scope="col">{t("tut.24")}</th><th scope="col">{t("tut.25")}</th>
              {(Object.keys(BANDS) as Band[]).map((b) => <th scope="col" key={b}>{t(BANDS[b])}</th>)}<th scope="col">{t("tut.26")}</th></tr></thead>
            <tbody>
              {map.concepts.map((row) => (
                <tr key={row.concept_id}>
                  <th scope="row">{row.label}</th><td>{cell(row.students)}</td>
                  {(Object.keys(BANDS) as Band[]).map((b) => <td key={b}>{row.bands ? cell(row.bands[b]) : "—"}</td>)}
                  <td>{row.needs_review_rate === null ? "—" : `${Math.round(row.needs_review_rate * 100)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p><small>{t("tut.27")}</small></p>
          {map.items.length > 0 && (
            <table>
              <caption>{t("tut.29")}</caption>
              <thead><tr><th scope="col">{t("tut.29")}</th><th scope="col">{t("tut.30")}</th></tr></thead>
              <tbody>{map.items.map((item) => (
                <tr key={item.item_id}><th scope="row">{item.prompt}</th><td>{item.first_try_rate === null ? cell(item.attempts) : `${Math.round(item.first_try_rate * 100)}%`}</td></tr>
              ))}</tbody>
            </table>
          )}
          <p><a href={`/v1/learning/mastery/offerings/${offeringId}/map.csv`} download>{t("tut.28")}</a></p>
        </>
      )}
    </section>
  );
}
