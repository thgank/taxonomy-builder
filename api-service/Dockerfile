# ── Stage 1: Build ────────────────────────────────────────
FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn package -DskipTests -B

# ── Stage 2: Runtime ─────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

RUN addgroup -S app && adduser -S app -G app
COPY --from=builder /build/target/*.jar app.jar
RUN mkdir -p /data/uploads && chown -R app:app /data/uploads

USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
