#!/bin/bash

# Script for running helper Docker

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <docker network>" >&2
  exit 1
fi

docker run --rm --sysctl net.ipv6.conf.all.disable_ipv6=0 --cap-add=NET_ADMIN --cap-add=NET_RAW --rm -it --network $1 ct-itmo/labs-net-helper bash
