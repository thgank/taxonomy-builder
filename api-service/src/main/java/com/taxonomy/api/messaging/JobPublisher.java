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

    public void publishImport(PipelineMessage message) {
        publish(RabbitConfig.RK_IMPORT, message);
    }

    public void publishNlp(PipelineMessage message) {
        publish(RabbitConfig.RK_NLP, message);
    }

    public void publishTerms(PipelineMessage message) {
        publish(RabbitConfig.RK_TERMS, message);
    }

    public void publishBuild(PipelineMessage message) {
        publish(RabbitConfig.RK_BUILD, message);
    }

    public void publishEvaluate(PipelineMessage message) {
        publish(RabbitConfig.RK_EVALUATE, message);
    }

    private void publish(String routingKey, PipelineMessage message) {
        log.info("Publishing to {}: jobId={}, correlationId={}",
                routingKey, message.jobId(), message.correlationId());
        rabbitTemplate.convertAndSend(RabbitConfig.EXCHANGE, routingKey, message);
    }
}
