package com.taxonomy.api.dto.request;

public record UpdateEdgeRequest(
        Double score,
        Boolean approved
) {}
