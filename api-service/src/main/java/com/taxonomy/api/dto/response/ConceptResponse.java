package com.taxonomy.api.dto.response;

import java.util.List;
import java.util.UUID;

public record ConceptResponse(
        UUID id,
        String canonical,
        List<String> surfaceForms,
        String lang,
        Double score
) {}
