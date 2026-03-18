const dateTimeFormatter = new Intl.DateTimeFormat("en", {
  dateStyle: "medium",
  timeStyle: "short",
});

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Not available";
  }

  return dateTimeFormatter.format(new Date(value));
}

export function formatFileSize(bytes: number | null | undefined) {
  if (!bytes) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

export function formatJsonCompact(value: Record<string, unknown> | null | undefined) {
  if (!value || Object.keys(value).length === 0) {
    return "No parameters";
  }

  return JSON.stringify(value, null, 2);
}

export function pluralize(count: number, singular: string, plural: string) {
  return `${count} ${count === 1 ? singular : plural}`;
}
