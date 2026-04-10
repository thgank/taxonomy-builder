package com.taxonomy.api.messaging;

import com.taxonomy.api.config.RabbitConfig;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

import java.util.Map;
import java.util.UUID;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class JobPublisherTest {

    @Test
    void publish_sendsMessageToTaxonomyExchange() {
        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        JobPublisher publisher = new JobPublisher(rabbitTemplate);
        PipelineMessage message = PipelineMessage.of(
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                "FULL_PIPELINE",
                Map.of("chunk_size", 1000),
                "corr-1",
                "trace-1"
        );

        publisher.publish("build", message);

        verify(rabbitTemplate).convertAndSend(RabbitConfig.EXCHANGE, "build", message);
    }
}
