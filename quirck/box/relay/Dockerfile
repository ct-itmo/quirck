FROM debian:trixie-slim
RUN apt-get update -q && apt-get install -qy --no-install-recommends openvpn iptables curl tcpdump net-tools iputils-ping
ADD . /app
EXPOSE 1194
CMD ["/app/start.sh"]
