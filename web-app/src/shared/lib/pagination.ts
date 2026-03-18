type SearchValue = string | string[];

export interface Page<T> {
  content: T[];
  totalElements: number;
  totalPages: number;
  number: number;
  size: number;
  numberOfElements: number;
  first: boolean;
  last: boolean;
  empty: boolean;
}

export interface PaginationInput {
  page?: number;
  size?: number;
  sort?: string[];
}

export interface SearchParamsLike {
  [key: string]: SearchValue | SearchValue[] | undefined;
}

export function normalizePage<T>(value: Partial<Page<T>> | null | undefined): Page<T> {
  return {
    content: value?.content ?? [],
    totalElements: value?.totalElements ?? 0,
    totalPages: value?.totalPages ?? 0,
    number: value?.number ?? 0,
    size: value?.size ?? 0,
    numberOfElements: value?.numberOfElements ?? 0,
    first: value?.first ?? true,
    last: value?.last ?? true,
    empty: value?.empty ?? true,
  };
}

function parsePositiveInt(value: string | undefined, fallback: number) {
  if (!value) {
    return fallback;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function toStringArray(value: SearchValue | SearchValue[] | undefined) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }

  if (value === undefined) {
    return [];
  }

  return [String(value)];
}

export function getPaginationFromSearchParams(
  searchParams: SearchParamsLike,
  defaults: { page?: number; size?: number } = {},
): PaginationInput {
  const page = parsePositiveInt(
    typeof searchParams.page === "string" ? searchParams.page : undefined,
    defaults.page ?? 0,
  );
  const size = parsePositiveInt(
    typeof searchParams.size === "string" ? searchParams.size : undefined,
    defaults.size ?? 10,
  );
  const sort = toStringArray(searchParams.sort);

  return {
    page,
    size,
    sort: sort.length > 0 ? sort : undefined,
  };
}

export function toBackendPageQuery(input: PaginationInput) {
  return {
    page: input.page ?? 0,
    size: input.size ?? 10,
    sort: input.sort,
  };
}
