package com.taxonomy.api.exception;

import com.taxonomy.api.dto.response.ErrorResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.validation.BeanPropertyBindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.support.MissingServletRequestPartException;

import java.lang.reflect.Method;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class GlobalExceptionHandlerTest {

    private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

    @Test
    void handleNotFound_returns404() {
        var response = handler.handleNotFound(new ResourceNotFoundException("Job", UUID.fromString("00000000-0000-0000-0000-000000000111")));

        assertEquals(HttpStatus.NOT_FOUND, response.getStatusCode());
        assertEquals(404, response.getBody().status());
        assertTrue(response.getBody().message().contains("Job"));
    }

    @Test
    void handleConflict_returns409() {
        var response = handler.handleConflict(new ConflictException("Already running"));

        assertEquals(HttpStatus.CONFLICT, response.getStatusCode());
        assertEquals("Already running", response.getBody().message());
    }

    @Test
    void handleBadRequest_returns400() {
        var response = handler.handleBadRequest(new IllegalArgumentException("bad payload"));

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        assertEquals("bad payload", response.getBody().message());
    }

    @Test
    void handleValidation_returns400WithFieldDetails() throws Exception {
        Method method = DummyController.class.getDeclaredMethod("submit", DummyPayload.class);
        MethodParameter parameter = new MethodParameter(method, 0);
        BeanPropertyBindingResult binding = new BeanPropertyBindingResult(new DummyPayload(""), "payload");
        binding.addError(new FieldError("payload", "name", "must not be blank"));

        MethodArgumentNotValidException ex = new MethodArgumentNotValidException(parameter, binding);

        var response = handler.handleValidation(ex);

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        assertTrue(response.getBody().message().contains("Validation failed"));
        assertTrue(response.getBody().message().contains("name: must not be blank"));
    }

    @Test
    void handleTypeMismatch_returnsParameterContext() {
        MethodArgumentTypeMismatchException ex = new MethodArgumentTypeMismatchException(
                "abc",
                Integer.class,
                "page",
                null,
                new IllegalArgumentException("NaN")
        );

        var response = handler.handleTypeMismatch(ex);

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        assertEquals("Invalid value for 'page': abc", response.getBody().message());
    }

    @Test
    void handleUploadLimit_returns413() {
        var response = handler.handleUploadLimit(new MaxUploadSizeExceededException(10));

        assertEquals(HttpStatus.PAYLOAD_TOO_LARGE, response.getStatusCode());
        assertEquals("File size exceeds the allowed limit", response.getBody().message());
    }

    @Test
    void handleMissingRequestPart_returns400() {
        var response = handler.handleMissingRequestPart(new MissingServletRequestPartException("files"));

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        assertEquals("Missing required multipart field: files", response.getBody().message());
    }

    @Test
    void handleGeneral_returns500() {
        var response = handler.handleGeneral(new RuntimeException("boom"));

        assertEquals(HttpStatus.INTERNAL_SERVER_ERROR, response.getStatusCode());
        ErrorResponse body = response.getBody();
        assertNotNull(body);
        assertEquals(500, body.status());
        assertEquals("Internal server error", body.message());
        assertNotNull(body.timestamp());
    }

    private static final class DummyController {
        @SuppressWarnings("unused")
        void submit(@Valid DummyPayload payload) {
        }
    }

    private record DummyPayload(@NotBlank String name) {
    }
}
