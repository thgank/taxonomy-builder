package com.taxonomy.api.dto.request;

import jakarta.validation.constraints.NotNull;

import java.util.Map;

public record CreateJobRequest(
        @NotNull String type,
        Map<String, Object> params
) {}
