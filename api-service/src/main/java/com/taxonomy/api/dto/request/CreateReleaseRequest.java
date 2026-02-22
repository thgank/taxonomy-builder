package com.taxonomy.api.dto.request;

import java.util.UUID;

public record CreateReleaseRequest(
        UUID taxonomyVersionId,
        String releaseName,
        String channel,
        Integer trafficPercent,
        String notes
) {}
