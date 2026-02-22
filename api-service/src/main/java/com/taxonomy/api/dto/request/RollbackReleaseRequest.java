package com.taxonomy.api.dto.request;

import java.util.UUID;

public record RollbackReleaseRequest(
        UUID rollbackToReleaseId,
        String channel,
        String notes
) {}
