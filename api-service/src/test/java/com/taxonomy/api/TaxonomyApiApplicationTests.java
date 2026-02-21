package com.taxonomy.api;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class TaxonomyApiApplicationTests {

    @MockBean
    private RabbitTemplate rabbitTemplate;

    @Test
    void contextLoads() {
    }
}
