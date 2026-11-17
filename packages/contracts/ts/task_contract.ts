import { z } from "zod";

export const Confidence = z.enum(["high", "medium", "low"]);

export const Citation = z
  .object({
    doc_id: z.string().min(1).max(64),
    snippet: z.string().min(1).max(200),
  })
  .strict();

export const TaskInput = z
  .object({
    query_text: z.string().min(1).max(500),
    scope: z.enum(["tenant", "world"]),
    max_results: z.number().int().min(1).max(50).default(5),
  })
  .strict();

export const TaskOutput = z
  .object({
    answer: z.string().min(1).max(4000),
    citations: z.array(Citation).max(50).default([]),
    confidence: Confidence,
  })
  .strict();

export type TaskInputT = z.infer<typeof TaskInput>;
export type TaskOutputT = z.infer<typeof TaskOutput>;

export type FailureCode =
  | "PARSE_ERROR"
  | "MISSING_FIELD"
  | "ENUM_OUT_OF_RANGE"
  | "UNKNOWN_FIELD"
  | "TYPE_ERROR"
  | "CONSTRAINT_VIOLATION"
  | "RETRY_EXHAUSTED";

export interface ValidationResult {
  ok: boolean;
  code?: FailureCode;
  data?: TaskOutputT;
  raw: string;
  detail?: unknown[];
}

function mapIssues(issues: z.ZodIssue[]): FailureCode {
  const has = (pred: (issue: z.ZodIssue) => boolean) => issues.some(pred);

  if (has((i) => i.code === "invalid_type" && (i as z.ZodInvalidTypeIssue).received === "undefined")) {
    return "MISSING_FIELD";
  }
  if (has((i) => i.code === "invalid_enum_value")) return "ENUM_OUT_OF_RANGE";
  if (has((i) => i.code === "unrecognized_keys")) return "UNKNOWN_FIELD";
  if (has((i) => i.code === "too_small" || i.code === "too_big" || i.code === "invalid_string")) {
    return "CONSTRAINT_VIOLATION";
  }
  return "TYPE_ERROR";
}

export function validateTaskOutput(
  raw: string,
  maxResults = 50,
  allowedDocIds?: Set<string>,
): ValidationResult {
  let payload: unknown;
  try {
    payload = JSON.parse(raw);
  } catch (error) {
    return { ok: false, code: "PARSE_ERROR", raw, detail: [{ json: String(error) }] };
  }

  const parsed = TaskOutput.safeParse(payload);
  if (!parsed.success) {
    return { ok: false, code: mapIssues(parsed.error.issues), raw, detail: parsed.error.issues };
  }

  if (parsed.data.citations.length > maxResults) {
    return {
      ok: false,
      code: "CONSTRAINT_VIOLATION",
      raw,
      detail: [
        {
          constraint: "citations_exceed_max_results",
          got: parsed.data.citations.length,
          max: maxResults,
        },
      ],
    };
  }

  if (allowedDocIds) {
    const unknown = parsed.data.citations.map((c) => c.doc_id).filter((id) => !allowedDocIds.has(id));
    if (unknown.length > 0) {
      return {
        ok: false,
        code: "CONSTRAINT_VIOLATION",
        raw,
        detail: [{ constraint: "citation_not_from_tool_result", doc_ids: [...new Set(unknown)].sort() }],
      };
    }
  }

  return { ok: true, data: parsed.data, raw };
}