# The compiler builds the scheduler and the operators; the image carries
# them with kubectl, through which they talk to the cluster themselves.
FROM alpine:3.20 AS build
RUN apk add --no-cache build-base
WORKDIR /src
COPY . .
RUN make && mkdir -p /out \
 && bin/tc amaenetes.amae -o /out/amaenetes \
 && bin/tc kube/parting.amae -o /out/parting \
 && bin/tc kube/counsel.amae -o /out/counsel \
 && cp build/tc-core /out/tc-core

FROM alpine/k8s:1.35.9
COPY --from=build /out /opt/amae/bin
ENV HOME=/tmp
