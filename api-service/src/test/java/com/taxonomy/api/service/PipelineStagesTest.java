package com.taxonomy.api.service;

import com.taxonomy.api.entity.enums.JobType;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class PipelineStagesTest {

    @Test
    void stageHelpers_returnExpectedPipelineTopology() {
        assertEquals("import", PipelineStages.firstStage(JobType.FULL_PIPELINE));
        assertEquals("build", PipelineStages.firstStage(JobType.TAXONOMY));
        assertEquals("nlp", PipelineStages.nextStage(JobType.FULL_PIPELINE, "import"));
        assertNull(PipelineStages.nextStage(JobType.IMPORT, "import"));
        assertTrue(PipelineStages.isTerminal(JobType.FULL_PIPELINE, "evaluate"));
        assertFalse(PipelineStages.isTerminal(JobType.FULL_PIPELINE, "terms"));
    }

    @Test
    void firstStage_rejectsUnknownType() {
        assertThrows(NullPointerException.class, () -> PipelineStages.firstStage(null));
        assertThrows(NullPointerException.class, () -> PipelineStages.stagesFor(null));
    }
}
