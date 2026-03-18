import { z } from "zod";

const serverEnvSchema = z.object({
  TAXONOMY_API_BASE_URL: z.string().url(),
  TAXONOMY_API_KEY: z.string().min(1),
});

export const serverEnv = serverEnvSchema.parse({
  TAXONOMY_API_BASE_URL: process.env.TAXONOMY_API_BASE_URL,
  TAXONOMY_API_KEY: process.env.TAXONOMY_API_KEY,
});
