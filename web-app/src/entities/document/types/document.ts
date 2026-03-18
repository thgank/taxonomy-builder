export interface Document {
  id: string;
  collectionId: string;
  filename: string;
  mimeType: string;
  sizeBytes: number | null;
  status: "NEW" | "PARSED" | "FAILED";
  createdAt: string;
  parsedAt: string | null;
}

export interface DocumentChunk {
  id: string;
  documentId: string;
  chunkIndex: number;
  text: string;
  lang: string | null;
  charStart: number | null;
  charEnd: number | null;
}
