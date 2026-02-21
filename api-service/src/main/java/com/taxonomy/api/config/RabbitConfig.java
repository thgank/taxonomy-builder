package com.taxonomy.api.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitConfig {

    public static final String EXCHANGE   = "taxonomy";
    public static final String Q_IMPORT   = "taxonomy.import";
    public static final String Q_NLP      = "taxonomy.nlp";
    public static final String Q_TERMS    = "taxonomy.terms";
    public static final String Q_BUILD    = "taxonomy.build";
    public static final String Q_EVALUATE = "taxonomy.evaluate";

    public static final String RK_IMPORT   = "import";
    public static final String RK_NLP      = "nlp";
    public static final String RK_TERMS    = "terms";
    public static final String RK_BUILD    = "build";
    public static final String RK_EVALUATE = "evaluate";

    // DLQ
    public static final String DLX        = "taxonomy.dlx";
    public static final String DLQ        = "taxonomy.dlq";

    /* ── Exchange ────────────────────────────────────────── */

    @Bean
    public DirectExchange taxonomyExchange() {
        return new DirectExchange(EXCHANGE, true, false);
    }

    @Bean
    public FanoutExchange deadLetterExchange() {
        return new FanoutExchange(DLX, true, false);
    }

    /* ── Queues ──────────────────────────────────────────── */

    private Queue durableQueue(String name) {
        return QueueBuilder.durable(name)
                .withArgument("x-dead-letter-exchange", DLX)
                .withArgument("x-message-ttl", 300_000)    // 5 min retry delay
                .build();
    }

    @Bean public Queue importQueue()   { return durableQueue(Q_IMPORT);   }
    @Bean public Queue nlpQueue()      { return durableQueue(Q_NLP);      }
    @Bean public Queue termsQueue()    { return durableQueue(Q_TERMS);    }
    @Bean public Queue buildQueue()    { return durableQueue(Q_BUILD);    }
    @Bean public Queue evaluateQueue() { return durableQueue(Q_EVALUATE); }
    @Bean public Queue deadLetterQueue() {
        return QueueBuilder.durable(DLQ).build();
    }

    /* ── Bindings ────────────────────────────────────────── */

    @Bean public Binding bindImport()   { return BindingBuilder.bind(importQueue()).to(taxonomyExchange()).with(RK_IMPORT);     }
    @Bean public Binding bindNlp()      { return BindingBuilder.bind(nlpQueue()).to(taxonomyExchange()).with(RK_NLP);           }
    @Bean public Binding bindTerms()    { return BindingBuilder.bind(termsQueue()).to(taxonomyExchange()).with(RK_TERMS);       }
    @Bean public Binding bindBuild()    { return BindingBuilder.bind(buildQueue()).to(taxonomyExchange()).with(RK_BUILD);       }
    @Bean public Binding bindEvaluate() { return BindingBuilder.bind(evaluateQueue()).to(taxonomyExchange()).with(RK_EVALUATE); }
    @Bean public Binding bindDlq()      { return BindingBuilder.bind(deadLetterQueue()).to(deadLetterExchange());               }

    /* ── Template with JSON converter ────────────────────── */

    @Bean
    public Jackson2JsonMessageConverter messageConverter() {
        return new Jackson2JsonMessageConverter();
    }

    @Bean
    public RabbitTemplate rabbitTemplate(ConnectionFactory cf,
                                         Jackson2JsonMessageConverter converter) {
        var tpl = new RabbitTemplate(cf);
        tpl.setMessageConverter(converter);
        return tpl;
    }
}
