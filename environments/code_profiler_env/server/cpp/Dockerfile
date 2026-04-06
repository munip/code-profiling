FROM alpine:3.19 AS builder

WORKDIR /build

RUN apk add --no-cache cmake make g++

COPY ./src /build/src
COPY ./CMakeLists.txt /build/

RUN mkdir -p build && cd build && \
    cmake .. && \
    make

FROM alpine:3.19

WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY --from=builder /build/build/ecommerce_api /app/

ENV AUSTIN_ENABLED=true
ENV PROFILE_DURATION=5

EXPOSE 8080

CMD ["./ecommerce_api"]
