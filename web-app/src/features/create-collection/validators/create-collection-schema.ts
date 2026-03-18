import { z } from "zod";

export const createCollectionSchema = z.object({
  name: z.string().trim().min(1, "Collection name is required.").max(255),
  description: z.string().trim().max(4000).optional(),
});

export type CreateCollectionFormValues = z.infer<typeof createCollectionSchema>;
