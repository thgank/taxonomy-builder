import { z } from "zod";

import { jobTypes } from "@/entities/job/types/job";

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export const createJobSchema = z.object({
  type: z.enum(jobTypes),
  paramsText: z.string().trim().superRefine((value, context) => {
    if (!value) {
      return;
    }

    try {
      const parsed = JSON.parse(value);

      if (!isObjectRecord(parsed)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Parameters must be a JSON object.",
        });
      }
    } catch {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Parameters must be valid JSON.",
      });
    }
  }),
});

export type CreateJobFormValues = z.infer<typeof createJobSchema>;

export function parseJobParams(paramsText: string) {
  if (!paramsText.trim()) {
    return {};
  }

  return JSON.parse(paramsText) as Record<string, unknown>;
}
