import React from "react";

// A number as written in Vietnamese sources: 580.500 · 2,5 · 15/12/2026 · 20%.
const NUMBER = /\d+(?:[.,/]\d+)*%?/g;

/** The numbers of a text, as written and without separators, so "580.500" in the answer finds "580.500" or "580500" in the source. */
export function numbersOf(text: string): Set<string> {
  const out = new Set<string>();
  for (const match of text.matchAll(NUMBER)) {
    out.add(match[0]);
    out.add(match[0].replace(/[.,]/g, ""));
  }
  return out;
}

/**
 * The quote with every number that also appears in the answer wrapped in <mark>. The answer's statements passed the code check
 * that their numbers, dates and amounts are in the cited source, so a marked number is where the answer rests on this passage.
 */
export function markNumbers(quote: string, answer: string): { nodes: React.ReactNode[]; marked: number } {
  const wanted = numbersOf(answer);
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let marked = 0;
  for (const match of quote.matchAll(NUMBER)) {
    const value = match[0];
    const start = match.index ?? 0;
    // Single digits (list numbers, "Điều 1") are too common to mean anything on their own.
    if (value.replace(/\D/g, "").length < 2 || !(wanted.has(value) || wanted.has(value.replace(/[.,]/g, "")))) continue;
    if (start > last) nodes.push(quote.slice(last, start));
    nodes.push(<mark key={`m${start}`}>{value}</mark>);
    marked += 1;
    last = start + value.length;
  }
  if (last < quote.length) nodes.push(quote.slice(last));
  return { nodes, marked };
}
