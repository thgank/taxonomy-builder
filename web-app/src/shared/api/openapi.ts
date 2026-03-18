import type { components, operations } from "@/shared/api/generated/openapi";

export type ApiSchemas = components["schemas"];
export type OperationId = keyof operations;

type OperationResponses<T extends OperationId> = operations[T]["responses"];

export type ApiResponse<
  T extends OperationId,
  S extends keyof OperationResponses<T>,
> = OperationResponses<T>[S] extends {
  content: infer Content;
}
  ? Content extends { "*/*": infer Payload }
    ? Payload
    : Content extends { "application/json": infer Payload }
      ? Payload
      : never
  : never;

export type ApiJsonRequest<T extends OperationId> = operations[T] extends {
  requestBody?: {
    content: {
      "application/json": infer Payload;
    };
  };
}
  ? Payload
  : never;
