"""Stand-in for your real deploy code: 500 groups/services/policies via requests."""
import requests

DOMAIN = "/policy/api/v1/infra/domains/default"


def build_objects(n_groups=200, n_services=150, n_policies=150):
    objs = []
    for i in range(n_groups):
        objs.append((f"{DOMAIN}/groups/grp-{i:03d}", {
            "display_name": f"grp-{i:03d}",
            "expression": [{"resource_type": "IPAddressExpression",
                            "ip_addresses": [f"10.0.{i // 250}.{i % 250 + 1}"]}],
        }))
    for i in range(n_services):
        objs.append((f"/policy/api/v1/infra/services/svc-{i:03d}", {
            "display_name": f"svc-{i:03d}",
            "service_entries": [{"resource_type": "L4PortSetServiceEntry", "id": "e1",
                                 "l4_protocol": "TCP", "destination_ports": [str(1000 + i)]}],
        }))
    for i in range(n_policies):
        objs.append((f"{DOMAIN}/security-policies/pol-{i:03d}", {
            "display_name": f"pol-{i:03d}",
            "category": "Application",
            "rules": [{"id": "r1", "display_name": "allow", "action": "ALLOW",
                       "source_groups": [f"{DOMAIN}/groups/grp-{i:03d}"],
                       "services": [f"/infra/services/svc-{i:03d}"]}],
        }))
    return objs


def deploy(base_url, user="admin", password="secret"):
    s = requests.Session()
    s.auth = (user, password)
    for path, body in build_objects():
        s.patch(base_url + path, json=body).raise_for_status()
