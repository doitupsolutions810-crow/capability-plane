"""Provider factory — generic | kubernetes | cloud into SuspendTenantService."""
from __future__ import annotations
import os
from typing import Any
from .base import LookupResult
from .generic import GenericProviderAdapter
from .kubernetes_adapter import KubernetesProviderAdapter

class CloudProviderAdapter:
    name = "cloud"
    def __init__(self) -> None:
        self._inner = GenericProviderAdapter()
    def lookup(self, provider_request_id: str) -> LookupResult:
        return self._inner.lookup(provider_request_id)
    def isolate_or_mutate(self, provider_request_id: str, action: str, resource: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._inner.isolate_or_mutate(provider_request_id, action, resource, arguments)

def get_provider(name: str | None = None):
    key = (name or os.environ.get("PROVIDER_ADAPTER", "generic")).lower().strip()
    if key in ("k8s", "kubernetes"):
        allow = os.environ.get("K8S_NAMESPACE_ALLOWLIST", "admin-system,operations")
        return KubernetesProviderAdapter(namespace_allowlist={x.strip() for x in allow.split(",") if x.strip()})
    if key == "cloud":
        return CloudProviderAdapter()
    return GenericProviderAdapter()

def build_suspend_service():
    from admin.admin_action import AdminActionOrchestrator
    from admin.durable_outbox import DurableOutbox
    from admin.reconcile import Reconciler
    from admin.suspend_tenant import SuspendTenantService
    provider = get_provider()
    reconciler = Reconciler(lookup_fn=lambda pid: provider.lookup(pid).as_reconciler_dict())
    def mutate(provider_request_id: str, req):
        return provider.isolate_or_mutate(provider_request_id, req.action, req.resource, req.arguments)
    orch = AdminActionOrchestrator(reconciler=reconciler, mutate_fn=mutate)
    orch.outbox = DurableOutbox()
    return SuspendTenantService(provider=provider, orch=orch)
