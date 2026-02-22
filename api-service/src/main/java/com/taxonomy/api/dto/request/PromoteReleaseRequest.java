package com.taxonomy.api.dto.request;

public record PromoteReleaseRequest(
        String channel,
        Integer trafficPercent,
        String notes
) {}
