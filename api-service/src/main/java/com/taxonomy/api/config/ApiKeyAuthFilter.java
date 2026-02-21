package com.taxonomy.api.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.preauth.PreAuthenticatedAuthenticationToken;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;

public class ApiKeyAuthFilter extends OncePerRequestFilter {

    private static final String HEADER = "X-API-Key";
    private final String expectedKey;

    public ApiKeyAuthFilter(String expectedKey) {
        this.expectedKey = expectedKey;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain)
            throws ServletException, IOException {

        String providedKey = request.getHeader(HEADER);

        if (providedKey != null && timingSafeEquals(expectedKey, providedKey)) {
            var auth = new PreAuthenticatedAuthenticationToken(
                    "api-user", null, List.of());
            var ctx = SecurityContextHolder.createEmptyContext();
            ctx.setAuthentication(auth);
            SecurityContextHolder.setContext(ctx);
        }

        filterChain.doFilter(request, response);
    }

    /**
     * Constant-time comparison to prevent timing attacks on API key.
     */
    private static boolean timingSafeEquals(String expected, String provided) {
        byte[] a = expected.getBytes(StandardCharsets.UTF_8);
        byte[] b = provided.getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(a, b);
    }
}
