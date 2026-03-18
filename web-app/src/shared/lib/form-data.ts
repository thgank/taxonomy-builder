export function getString(formData: FormData, key: string) {
  const value = formData.get(key);

  if (typeof value !== "string") {
    return "";
  }

  return value.trim();
}

export function getOptionalString(formData: FormData, key: string) {
  const value = getString(formData, key);
  return value.length > 0 ? value : undefined;
}

export function getOptionalNumber(formData: FormData, key: string) {
  const value = getOptionalString(formData, key);

  if (!value) {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function getOptionalBoolean(formData: FormData, key: string) {
  return formData.get(key) === "on" ? true : undefined;
}

export function getFiles(formData: FormData, key: string) {
  return formData
    .getAll(key)
    .filter((value): value is File => value instanceof File && value.size > 0);
}
