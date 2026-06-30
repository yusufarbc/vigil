FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /bin/case-service ./cmd

FROM gcr.io/distroless/static-debian12
COPY --from=builder /bin/case-service /case-service
USER nonroot:nonroot
ENTRYPOINT ["/case-service"]
