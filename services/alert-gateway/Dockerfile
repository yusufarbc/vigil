FROM golang:1.22-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /bin/alert-gateway ./cmd

FROM gcr.io/distroless/static-debian12
COPY --from=builder /bin/alert-gateway /alert-gateway
USER nonroot:nonroot
ENTRYPOINT ["/alert-gateway"]
