"""Verificação de domínio customizado.

Provider abstraído para permitir integração DNS real no futuro e modo
manual de confirmação por SUPER_ADMIN em desenvolvimento.
"""


class DomainVerificationProvider:
    """Interface para verificação de registros TXT de domínio."""

    async def verify_txt(self, domain: str, token: str) -> bool:
        raise NotImplementedError


class MockDomainProvider(DomainVerificationProvider):
    """Provider mock que sempre retorna False.

    Em produção deve ser substituído por uma implementação real (DNS over
    HTTPS, resolver DNS, etc.). A confirmação manual por SUPER_ADMIN
    permanece disponível para desenvolvimento.
    """

    async def verify_txt(self, domain: str, token: str) -> bool:
        return False


def get_domain_verification_provider() -> DomainVerificationProvider:
    """Factory que retorna o provider configurado.

    Por padrão retorna o mock. Implementações reais podem ser registradas
    aqui conforme configuração de ambiente.
    """
    return MockDomainProvider()


def build_txt_record_name(domain: str) -> str:
    """Nome do registro TXT esperado para verificação de domínio."""
    return f"_wr-cursos-verification.{domain}"


def build_dns_instructions(domain: str, token: str) -> dict:
    """Retorna as instruções de configuração DNS para o tenant."""
    return {
        "record_type": "TXT",
        "host": build_txt_record_name(domain),
        "value": f"wr-cursos-verification={token}",
        "instructions": (
            "Adicione um registro TXT no DNS do domínio apontado e chame "
            "POST /api/v1/tenants/custom-domain/verify. Em ambientes sem "
            "DNS disponível, um SUPER_ADMIN pode confirmar manualmente via "
            "POST /api/v1/super-admin/tenants/{tenant_id}/custom-domain/confirm."
        ),
    }
