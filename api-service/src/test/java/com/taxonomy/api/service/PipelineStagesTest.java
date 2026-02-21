package com.taxonomy.api.service;

import com.taxonomy.api.entity.enums.JobType;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class PipelineStagesTest {

    @Test
    void fullPipeline_hasAllStages() {
        List<String> stages = PipelineStages.stagesFor(JobType.FULL_PIPELINE);
        assertEquals(List.of("import", "nlp", "terms", "build", "evaluate"), stages);
    }

    @Test
    void importJob_hasSingleStage() {
        assertEquals(List.of("import"), PipelineStages.stagesFor(JobType.IMPORT));
    }

    @Test
    void firstStage_fullPipeline_isImport() {
        assertEquals("import", PipelineStages.firstStage(JobType.FULL_PIPELINE));
    }

    @Test
    void firstStage_taxonomy_isBuild() {
        assertEquals("build", PipelineStages.firstStage(JobType.TAXONOMY));
    }

    @Test
    void nextStage_importToNlp() {
        assertEquals("nlp", PipelineStages.nextStage(JobType.FULL_PIPELINE, "import"));
    }

    @Test
    void nextStage_nlpToTerms() {
        assertEquals("terms", PipelineStages.nextStage(JobType.FULL_PIPELINE, "nlp"));
    }

    @Test
    void nextStage_termsToBuild() {
        assertEquals("build", PipelineStages.nextStage(JobType.FULL_PIPELINE, "terms"));
    }

    @Test
    void nextStage_buildToEvaluate() {
        assertEquals("evaluate", PipelineStages.nextStage(JobType.FULL_PIPELINE, "build"));
    }

    @Test
    void nextStage_evaluate_isTerminal() {
        assertNull(PipelineStages.nextStage(JobType.FULL_PIPELINE, "evaluate"));
    }

    @Test
    void nextStage_singleStageJob_isTerminal() {
        assertNull(PipelineStages.nextStage(JobType.IMPORT, "import"));
        assertNull(PipelineStages.nextStage(JobType.NLP, "nlp"));
        assertNull(PipelineStages.nextStage(JobType.TERMS, "terms"));
        assertNull(PipelineStages.nextStage(JobType.TAXONOMY, "build"));
    }

    @Test
    void isTerminal_lastStage_true() {
        assertTrue(PipelineStages.isTerminal(JobType.FULL_PIPELINE, "evaluate"));
        assertTrue(PipelineStages.isTerminal(JobType.IMPORT, "import"));
    }

    @Test
    void isTerminal_middleStage_false() {
        assertFalse(PipelineStages.isTerminal(JobType.FULL_PIPELINE, "import"));
        assertFalse(PipelineStages.isTerminal(JobType.FULL_PIPELINE, "build"));
    }

    @Test
    void nextStage_unknownStage_returnsNull() {
        assertNull(PipelineStages.nextStage(JobType.FULL_PIPELINE, "nonexistent"));
    }
}
