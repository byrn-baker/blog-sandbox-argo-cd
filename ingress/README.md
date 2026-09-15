# Lab ingress

MetalLB assigns the ingress addresses and announces them with ARP on the
appropriate network. Traefik accepts HTTP/HTTPS connections at those addresses
and selects the application using the request hostname. MetalLB doesn't inspect
hostnames or serve DNS.

| Client network | Address | Announcing interface |
| --- | --- | --- |
| Management and home clients through pfSense | 192.168.3.240 | eth0 |
| Lab clients | 10.100.0.240 | bond0 |

Both addresses serve `https://grafana.sandbox.lab` and
`https://argocd.sandbox.lab`. HTTP redirects to HTTPS. Unknown HTTP hostnames on
the HTTPS listener return 404. Existing application authentication still applies.

## Ownership and deployment

The Argo CD root Application deploys `apps/09-metallb.yaml` through
`apps/12-ingress-routes.yaml`. Chart settings live in `values/`, address pools
and interface restrictions in `ingress/addresses/`, and application routing in
`ingress/routes/`. The bundled K3s Traefik and ServiceLB remain disabled; this
Traefik installation is managed explicitly through Argo CD.

There are two Traefik replicas, spread across worker hostnames and zones.
MetalLB speakers run on the six workers. Both LoadBalancer Services use
`externalTrafficPolicy: Cluster`, so forwarding can take an extra node hop and
doesn't preserve the original client address. Layer 2 advertisement elects an
announcing node for each VIP; this isn't BGP anycast.

In the sibling `blog-sandbox` repository, `service_endpoints.yml` declares the
VIPs and hostnames. The Git-sourced `LabIngressReservations` Nautobot job
reserves the two addresses without assigning them to a VM interface. Changes to
that source must also update the corresponding Argo address pools, Service
annotations and routes. Keep the VIPs outside any DHCP allocation ranges.

## DNS and workstation access

The `blog-sandbox/ansible/pb.dns.yml` playbook updates BIND from Nautobot and
`service_endpoints.yml`. It validates staged zones and configuration before
activating them. Run it using the existing Ansible inventory and Nautobot
credential environment:

```sh
cd /home/ubuntu/blog-sandbox/ansible
.ansible/bin/ansible-playbook pb.dns.yml -e bind_validate_only=true
.ansible/bin/ansible-playbook pb.dns.yml
```

BIND selects a DNS view from the source address of the query. Queries from
`10.0.0.0/8` or `fd10::/32` receive the lab VIP; other permitted sources receive
the management VIP. The answer follows the resolver's source address when a
client uses a forwarding resolver.

Home clients use pfSense, so configure **Services > DNS Resolver > Domain
Overrides** with domain `sandbox.lab` and destination `192.168.3.71`, then
save and apply. This forwards that zone to BIND while retaining pfSense's normal
resolution for other domains. See the [pfSense domain override documentation](https://docs.netgate.com/pfsense/en/latest/services/dns/resolver-domain-overrides.html).

The pfSense override wasn't configured during this rollout because management
access wasn't available. A direct query to pfSense still returned NXDOMAIN.
After configuring it, verify from the workstation:

```sh
nslookup grafana.sandbox.lab
nslookup argocd.sandbox.lab
```

Both should return `192.168.3.240`. DNS doesn't create IP reachability: the
client must be able to reach this management address through its gateway.
The known workstation `192.168.100.32` has a return host route through
`192.168.3.1` on the K3s VMs; access from other home addresses hasn't been
verified. No border-router port forward was added for this management path.

## Certificates

Import [lab-ingress-ca.crt](lab-ingress-ca.crt) into the workstation/browser's
trusted certificate authorities. This is a private lab CA, so browsers won't
trust it automatically. Only the public CA certificate is in Git.

`python3 tools/ingress_tls.py` creates or reuses local keys and publishes the
TLS Secrets without committing private material. Run it after Argo creates
the Traefik namespace. It renews the ingress certificate when fewer than
30 days remain and expands its names when routes change. Renewal isn't
scheduled automatically; check expiry and rerun the tool before it expires.
Retain a secure backup of the local PKI state to preserve the trusted CA.

Traefik verifies the Argo backend certificate using `argocd-backend-ca` and
the server name `argocd-server`. Rerun the same tool after rotating Argo's
backend certificate. Grafana uses HTTP on its internal ClusterIP Service.

## Rollout verification

All ten Argo Applications were Healthy/Synced, all nine K3s nodes were Ready,
both Traefik replicas were available, and all six MetalLB speakers were Ready.
Both HTTPS hostnames passed certificate and hostname validation through the
management VIP and through the lab VIP from one VM in each datacenter.

Authenticated Grafana dashboard and Argo application API requests returned
200. Unauthenticated protected API requests returned 401. HTTP returned a
308 redirect to the HTTPS hostname; an unknown host returned 404. The existing
Grafana NodePort at `192.168.3.66:30300` still returned 200 for `/login`.

BIND returned the correct address from each view, retained an existing device
record, and resolved an external name. An intentionally invalid staged DNS
name was rejected before activation. These checks didn't test a cold boot,
datacenter failure, maximum throughput, or access from the user's workstation.
