package com.taxonomy.api.dto.response;

import java.util.List;
import java.util.UUID;

public record TaxonomyTreeResponse(
        UUID taxonomyVersionId,
        List<TreeNode> roots
) {
    public record TreeNode(
            UUID conceptId,
            String label,
            Double score,
            List<TreeNode> children
    ) {}
}
