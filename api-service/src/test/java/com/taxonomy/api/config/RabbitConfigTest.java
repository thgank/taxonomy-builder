package com.taxonomy.api.config;

import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;

class RabbitConfigTest {

    private final RabbitConfig config = new RabbitConfig();

    @Test
    void queueBeans_areDurableAndCarryRetryArguments() {
        Queue importQueue = config.importQueue();
        Queue buildQueue = config.buildQueue();
        Queue dlq = config.deadLetterQueue();

        assertTrue(importQueue.isDurable());
        assertEquals(RabbitConfig.DLX, importQueue.getArguments().get("x-dead-letter-exchange"));
        assertEquals(300_000, importQueue.getArguments().get("x-message-ttl"));
        assertEquals(RabbitConfig.Q_BUILD, buildQueue.getName());
        assertTrue(dlq.isDurable());
        assertTrue(dlq.getArguments() == null || dlq.getArguments().isEmpty());
    }

    @Test
    void bindings_connectQueuesToExpectedExchangeAndRoutingKey() {
        Binding importBinding = config.bindImport();
        Binding nlpBinding = config.bindNlp();
        Binding termsBinding = config.bindTerms();
        Binding buildBinding = config.bindBuild();
        Binding evaluateBinding = config.bindEvaluate();
        Binding dlqBinding = config.bindDlq();

        assertBinding(importBinding, RabbitConfig.Q_IMPORT, RabbitConfig.EXCHANGE, RabbitConfig.RK_IMPORT);
        assertBinding(nlpBinding, RabbitConfig.Q_NLP, RabbitConfig.EXCHANGE, RabbitConfig.RK_NLP);
        assertBinding(termsBinding, RabbitConfig.Q_TERMS, RabbitConfig.EXCHANGE, RabbitConfig.RK_TERMS);
        assertBinding(buildBinding, RabbitConfig.Q_BUILD, RabbitConfig.EXCHANGE, RabbitConfig.RK_BUILD);
        assertBinding(evaluateBinding, RabbitConfig.Q_EVALUATE, RabbitConfig.EXCHANGE, RabbitConfig.RK_EVALUATE);
        assertEquals(RabbitConfig.DLQ, dlqBinding.getDestination());
        assertEquals(RabbitConfig.DLX, dlqBinding.getExchange());
    }

    @Test
    void rabbitTemplate_usesJsonMessageConverter() {
        ConnectionFactory connectionFactory = mock(ConnectionFactory.class);
        Jackson2JsonMessageConverter converter = config.messageConverter();

        RabbitTemplate template = config.rabbitTemplate(connectionFactory, converter);

        assertSame(converter, template.getMessageConverter());
        assertNotNull(config.taxonomyExchange());
        assertNotNull(config.deadLetterExchange());
    }

    private static void assertBinding(Binding binding, String destination, String exchange, String routingKey) {
        assertEquals(destination, binding.getDestination());
        assertEquals(exchange, binding.getExchange());
        assertEquals(routingKey, binding.getRoutingKey());
    }
}
