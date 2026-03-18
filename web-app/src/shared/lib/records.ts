export type UnknownRecord = Record<string, unknown>;

export function toUnknownRecord(value: unknown): UnknownRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  return value as UnknownRecord;
}

export function toUnknownRecordArray(value: unknown): UnknownRecord[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => toUnknownRecord(item))
    .filter((item): item is UnknownRecord => item !== null);
}
