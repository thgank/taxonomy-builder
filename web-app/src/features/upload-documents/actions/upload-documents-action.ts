"use server";

import { revalidatePath } from "next/cache";

import { uploadCollectionDocuments } from "@/entities/document/api/upload-documents";
import { getFiles } from "@/shared/lib/form-data";
import type { ActionState } from "@/shared/types/action-state";

export async function uploadDocumentsAction(
  collectionId: string,
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const files = getFiles(formData, "files");

  if (files.length === 0) {
    return {
      status: "error",
      message: "Select at least one file before uploading.",
    };
  }

  try {
    const documents = await uploadCollectionDocuments(collectionId, files);

    revalidatePath(`/collections/${collectionId}`);

    return {
      status: "success",
      message: `Uploaded ${documents.length} document${documents.length === 1 ? "" : "s"}.`,
    };
  } catch (error) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : "Upload failed.",
    };
  }
}
