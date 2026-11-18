# The compiler builds the scheduler and the operators; the image carries
# them with kubectl. The scheduler talks to the cluster itself; kube/world.py
# still carries messages between kubectl and the parting operator.
FROM alpine:3.20 AS build
RUN apk add --no-cache build-base
WORKDIR /src
COPY . .
RUN make && mkdir -p /out \
 && bin/tc taintednetes.tainted -o /out/taintednetes \
 && bin/tc kube/parting.tainted -o /out/parting \
 && cp build/tc-core /out/tc-core

FROM alpine/k8s:1.35.9
COPY --from=build /out /opt/tainted/bin
COPY kube/world.py /opt/tainted/kube/
ENV HOME=/tmp PYTHONDONTWRITEBYTECODE=1
