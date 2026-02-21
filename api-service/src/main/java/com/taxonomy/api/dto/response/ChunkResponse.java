package com.taxonomy.api.dto.response;

import java.util.UUID;

public record ChunkResponse(
        UUID id,
        UUID documentId,
        int chunkIndex,
        String text,
        String lang,
        Integer charStart,
        Integer charEnd
) {}
