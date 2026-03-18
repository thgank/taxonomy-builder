export interface Collection {
  id: string;
  name: string;
  description: string | null;
  createdAt: string;
  documentCount: number;
}

export interface CreateCollectionRequest {
  name: string;
  description?: string;
}
