#!/bin/bash

source /run/network.env
ip=${trusted_ip:-$trusted_ip6}
interface=mv-$(echo "${trusted_ip:-$trusted_ip6}:$trusted_port" | md5sum | head -c 12)
network=${UV_NETWORK:-$NETWORK_DEFAULT}
var_name="NETWORK_HWADDR_$network"

if [[ -z "${!var_name}" ]]; then
    echo "No such network: $network"
    exit 1
fi

ip link show $interface || {
    ip link add $interface link $dev type macvlan mode source
    ip link set $interface up
    ip link set $interface promisc on
    ip link set $interface master br-$network
}
