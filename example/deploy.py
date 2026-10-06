"""Stand-in for your real deploy code: 500 groups/services/policies via requests."""
import requests


class NSXObjectFactory:
    """Builds the (path, body) pairs to deploy."""

    DOMAIN = "/policy/api/v1/infra/domains/default"

    def __init__(self, n_groups=200, n_services=150, n_policies=150):
        self.n_groups = n_groups
        self.n_services = n_services
        self.n_policies = n_policies

    def groups(self):
        for i in range(self.n_groups):
            yield f"{self.DOMAIN}/groups/grp-{i:03d}", {
                "display_name": f"grp-{i:03d}",
                "expression": [{"resource_type": "IPAddressExpression",
                                "ip_addresses": [f"10.0.{i // 250}.{i % 250 + 1}"]}],
            }

    def services(self):
        for i in range(self.n_services):
            yield f"/policy/api/v1/infra/services/svc-{i:03d}", {
                "display_name": f"svc-{i:03d}",
                "service_entries": [{"resource_type": "L4PortSetServiceEntry", "id": "e1",
                                     "l4_protocol": "TCP", "destination_ports": [str(1000 + i)]}],
            }

    def policies(self):
        for i in range(self.n_policies):
            yield f"{self.DOMAIN}/security-policies/pol-{i:03d}", {
                "display_name": f"pol-{i:03d}",
                "category": "Application",
                "rules": [{"id": "r1", "display_name": "allow", "action": "ALLOW",
                           "source_groups": [f"{self.DOMAIN}/groups/grp-{i:03d}"],
                           "services": [f"/infra/services/svc-{i:03d}"]}],
            }

    def __iter__(self):
        yield from self.groups()
        yield from self.services()
        yield from self.policies()


class NSXDeployer:
    def __init__(self, base_url, user="admin", password="secret", factory=None):
        self.base_url = base_url
        self.factory = factory or NSXObjectFactory()
        self.session = requests.Session()
        self.session.auth = (user, password)

    def deploy(self) -> None:
        for path, body in self.factory:
            self.session.patch(self.base_url + path, json=body).raise_for_status()
