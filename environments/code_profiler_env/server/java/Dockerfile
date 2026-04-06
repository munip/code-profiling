FROM eclipse-temurin:17-jdk-alpine

WORKDIR /app

RUN apk add --no-cache curl

RUN mkdir -p /opt/async-profiler && \
    curl -L https://github.com/async-profiler/async-profiler/releases/download/v4.3/async-profiler-4.3-linux-x64.tar.gz | \
    tar -xz -C /opt/async-profiler --strip-components=1

ENV JAVA_HOME=/opt/java/openjdk
ENV PATH=$PATH:/opt/async-profiler

COPY ./src /app/src

RUN javac -d /app/classes /app/src/**/*.java

ENV ASYNC_PROFILER_HOME=/opt/async-profiler
ENV PROFILE_DURATION=5

EXPOSE 8080

CMD ["java", "-cp", "/app/classes", "com.ecommerce.api.ECommerceAPI"]
