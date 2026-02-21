package com.taxonomy.api.dto.response;

import java.time.Instant;
import java.util.UUID;

public record DocumentResponse(
        UUID id,
        UUID collectionId,
        String filename,
        String mimeType,
        Long sizeBytes,
        String status,
        Instant createdAt,
        Instant parsedAt
) {}
