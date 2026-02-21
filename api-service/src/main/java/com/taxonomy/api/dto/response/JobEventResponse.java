package com.taxonomy.api.dto.response;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

public record JobEventResponse(
        UUID id,
        Instant ts,
        String level,
        String message,
        Map<String, Object> meta
) {}
