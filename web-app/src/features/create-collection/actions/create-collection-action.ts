"use server";

import { revalidatePath } from "next/cache";

import { createCollection } from "@/entities/collection/api/create-collection";
import type { CreateCollectionFormValues } from "@/features/create-collection/validators/create-collection-schema";
import { createCollectionSchema } from "@/features/create-collection/validators/create-collection-schema";
import { isApiError } from "@/shared/api/error";

export interface CreateCollectionActionResult {
  success: boolean;
  collectionId?: string;
  message?: string;
  fieldErrors?: Partial<Record<keyof CreateCollectionFormValues, string>>;
}

export async function createCollectionAction(
  input: CreateCollectionFormValues,
): Promise<CreateCollectionActionResult> {
  const parsed = createCollectionSchema.safeParse(input);

  if (!parsed.success) {
    return {
      success: false,
      fieldErrors: {
        name: parsed.error.flatten().fieldErrors.name?.[0],
        description: parsed.error.flatten().fieldErrors.description?.[0],
      },
      message: "Please correct the highlighted fields.",
    };
  }

  try {
    const collection = await createCollection({
      name: parsed.data.name,
      description: parsed.data.description || undefined,
    });

    revalidatePath("/collections");

    return {
      success: true,
      collectionId: collection.id,
    };
  } catch (error) {
    return {
      success: false,
      message: isApiError(error) ? error.message : "Failed to create collection.",
    };
  }
}
