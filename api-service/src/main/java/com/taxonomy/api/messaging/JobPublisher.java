package com.taxonomy.api.messaging;

import com.taxonomy.api.config.RabbitConfig;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class JobPublisher {

    private static final Logger log = LoggerFactory.getLogger(JobPublisher.class);
    private final RabbitTemplate rabbitTemplate;

    public JobPublisher(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    /**
     * Publish a pipeline message to the given routing key (stage name).
     */
    public void publish(String routingKey, PipelineMessage message) {
        log.info("Publishing to {}: jobId={}, jobType={}, correlationId={}",
                routingKey, message.jobId(), message.jobType(), message.correlationId());
        rabbitTemplate.convertAndSend(RabbitConfig.EXCHANGE, routingKey, message);
    }
}
