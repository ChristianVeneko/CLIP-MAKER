import { parseClock } from "./time";

const TIME = String.raw`\d{1,2}(?::\d{1,2}){1,2}`;
const RANGE = new RegExp(
  String.raw`(?<![\w:.])(${TIME})(?:\s*[-–—]\s*|\s+(?:to|a|hasta|until)\s+)(${TIME})(?![\w:])`,
  "gi",
);

/**
 * Mirrors the backend rule: the text contains at least one explicit mm:ss range
 * (end after start). Only the colon form is checked here; the backend stays authoritative.
 */
export function hasExplicitRanges(text: string): boolean {
  for (const m of text.matchAll(RANGE)) {
    const a = parseClock(m[1]);
    const b = parseClock(m[2]);
    if (a !== null && b !== null && b > a) return true;
  }
  return false;
}
