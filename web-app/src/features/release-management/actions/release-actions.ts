"use server";

import { revalidatePath } from "next/cache";

import { createRelease } from "@/entities/release/api/create-release";
import { promoteRelease } from "@/entities/release/api/promote-release";
import { rollbackRelease } from "@/entities/release/api/rollback-release";
import { getOptionalNumber, getOptionalString } from "@/shared/lib/form-data";
import type { ActionState } from "@/shared/types/action-state";

export async function createReleaseAction(
  collectionId: string,
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  try {
    await createRelease(collectionId, {
      taxonomyVersionId: getOptionalString(formData, "taxonomyVersionId"),
      releaseName: getOptionalString(formData, "releaseName"),
      channel: getOptionalString(formData, "channel"),
      trafficPercent: getOptionalNumber(formData, "trafficPercent"),
      notes: getOptionalString(formData, "notes"),
    });

    revalidatePath(`/collections/${collectionId}`);

    return {
      status: "success",
      message: "Release created.",
    };
  } catch (error) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : "Failed to create release.",
    };
  }
}

export async function promoteReleaseAction(
  collectionId: string,
  releaseId: string,
  formData: FormData,
) {
  await promoteRelease(collectionId, releaseId, {
    channel: getOptionalString(formData, "channel"),
    trafficPercent: getOptionalNumber(formData, "trafficPercent"),
    notes: getOptionalString(formData, "notes"),
  });

  revalidatePath(`/collections/${collectionId}`);
}

export async function rollbackReleaseAction(
  collectionId: string,
  releaseId: string,
  formData: FormData,
) {
  await rollbackRelease(collectionId, releaseId, {
    rollbackToReleaseId: getOptionalString(formData, "rollbackToReleaseId"),
    channel: getOptionalString(formData, "channel"),
    notes: getOptionalString(formData, "notes"),
  });

  revalidatePath(`/collections/${collectionId}`);
}
