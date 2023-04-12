#!/bin/bash

ip=${trusted_ip:-$trusted_ip6}
interface=mv-$(echo "${trusted_ip:-$trusted_ip6}:$trusted_port" | md5sum | head -c 12)

if [[ "$1" == "delete" ]]; then
    ip link set link dev $interface type macvlan macaddr del ${2%%@*}
else
    ip link set link dev $interface type macvlan macaddr add ${2%%@*}
fi
