import type {
  Collection,
  CreateCollectionRequest,
} from "@/entities/collection/types/collection";
import { backendRequest } from "@/shared/api/backend-client";

export async function createCollection(payload: CreateCollectionRequest) {
  return backendRequest<Collection>("/api/collections", {
    method: "POST",
    body: payload,
  });
}
