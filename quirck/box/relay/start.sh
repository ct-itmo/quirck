#!/bin/bash

set -e

sed -i 's:$cert:'"$CERT"':g' /app/openvpn.conf
sed -i 's:$key:'"$KEY"':' /app/openvpn.conf

mkdir -p /logs

mkdir -p /dev/net
mknod /dev/net/tun c 10 200 || true

openvpn --config /app/openvpn.conf --daemon

sleep 5

echo "Interfaces:"
ip -br addr show

INTERNAL=$(ip -br addr show | awk -F' ' 'NF == 3' | grep eth | cut -f1 -d ' ' | cut -f1 -d@)
echo "Internal interface is $INTERNAL"

ip link set tap0 up

ip link add name br0 type bridge
ip link set br0 up
ip link set br0 promisc on

ip link set $INTERNAL promisc on
ip link set $INTERNAL master br0
ip link set tap0 promisc on
ip link set tap0 master br0

shutdown() {
  echo "Shutting down"
  exit 0
}

trap 'shutdown' SIGTERM

echo "It's alive, sleeping..."

while true; do
    sleep 123456 & wait $!
done
