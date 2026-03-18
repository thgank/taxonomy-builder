"use server";

import { revalidatePath } from "next/cache";

import { createTaxonomyEdge } from "@/entities/taxonomy/api/create-taxonomy-edge";
import { createTaxonomyLabel } from "@/entities/taxonomy/api/create-taxonomy-label";
import { deleteTaxonomyEdge } from "@/entities/taxonomy/api/delete-taxonomy-edge";
import { updateTaxonomyEdge } from "@/entities/taxonomy/api/update-taxonomy-edge";
import {
  getOptionalBoolean,
  getOptionalNumber,
  getOptionalString,
} from "@/shared/lib/form-data";
import type { ActionState } from "@/shared/types/action-state";

export async function createTaxonomyEdgeAction(
  taxonomyId: string,
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  try {
    await createTaxonomyEdge(taxonomyId, {
      parentConceptId: getOptionalString(formData, "parentConceptId") ?? "",
      childConceptId: getOptionalString(formData, "childConceptId") ?? "",
      relation: getOptionalString(formData, "relation"),
      score: getOptionalNumber(formData, "score"),
    });

    revalidatePath(`/taxonomies/${taxonomyId}`);

    return {
      status: "success",
      message: "Edge created.",
    };
  } catch (error) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : "Failed to create edge.",
    };
  }
}

export async function createTaxonomyLabelAction(
  taxonomyId: string,
  _prevState: ActionState,
  formData: FormData,
): Promise<ActionState> {
  try {
    await createTaxonomyLabel(taxonomyId, {
      candidateId: getOptionalString(formData, "candidateId"),
      parentConceptId: getOptionalString(formData, "parentConceptId"),
      childConceptId: getOptionalString(formData, "childConceptId"),
      parentLabel: getOptionalString(formData, "parentLabel"),
      childLabel: getOptionalString(formData, "childLabel"),
      label: getOptionalString(formData, "label"),
      labelSource: getOptionalString(formData, "labelSource"),
      reviewerId: getOptionalString(formData, "reviewerId"),
      reason: getOptionalString(formData, "reason"),
      meta: undefined,
    });

    revalidatePath(`/taxonomies/${taxonomyId}`);

    return {
      status: "success",
      message: "Label created.",
    };
  } catch (error) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : "Failed to create label.",
    };
  }
}

export async function updateTaxonomyEdgeAction(
  taxonomyId: string,
  edgeId: string,
  formData: FormData,
) {
  await updateTaxonomyEdge(taxonomyId, edgeId, {
    score: getOptionalNumber(formData, "score"),
    approved: getOptionalBoolean(formData, "approved"),
  });

  revalidatePath(`/taxonomies/${taxonomyId}`);
}

export async function deleteTaxonomyEdgeAction(taxonomyId: string, edgeId: string) {
  await deleteTaxonomyEdge(taxonomyId, edgeId);
  revalidatePath(`/taxonomies/${taxonomyId}`);
}
