package com.taxonomy.api.dto.response;

import java.time.Instant;
import java.util.UUID;

public record CollectionResponse(
        UUID id,
        String name,
        String description,
        Instant createdAt,
        long documentCount
) {}
