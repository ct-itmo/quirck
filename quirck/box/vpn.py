from datetime import datetime, timedelta

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.x509.extensions import AuthorityKeyIdentifier, BasicConstraints, SubjectKeyIdentifier
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

from quirck.core import config, s3


BASE = """client
dev tap
proto tcp
remote {host} {port}

nobind

cipher AES-256-GCM
auth SHA256
key-direction 1

{directives}
verb 3

<ca>
{ca_certificate}
</ca>

<cert>
{client_certificate}
</cert>

<key>
{client_key}
</key>

<tls-crypt>
-----BEGIN OpenVPN Static key V1-----
01368d28adc2b39e30cbc294977984cd
b09f2b0cf6ce480724478d4d8899d393
33bd57942935f442f3382738df5663ac
a5590bbce2ad2a0c04a600d6660b2812
125428229fa91a9f7ded14cc36b1b971
c912039d912891e956fe233e941f2eca
053942326c23ac3960c796ba70021df2
8a8aac62dcab6fc444fa8286a78261f4
508fa04cd047d654a2d9dc513443a635
d579332395b791964b18617c69afe071
7b093af19194a641f0fea71b3a39a49f
3dd044b36b75d3775ed227c993cdc080
cdec0554cc646b02bba8da59adef7407
b39ac4100ae197a7334fe38f6d2aab41
876d58bf8db153456a32a544a827d998
d7f09cb75297b3caea5beb810f8e5c5c
-----END OpenVPN Static key V1-----
</tls-crypt>
"""

LINUX_DIRECTIVES = """script-security 2
up "/usr/bin/env sh -c 'ip link set $dev up || ifconfig $dev up'"
up-restart
"""


def generate_key_pair(
    curve: ec.EllipticCurve,
    common_name: str,
    signing_key: ec.EllipticCurvePrivateKey | None,
    signing_issuer: x509.Name | None
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    private_key = ec.generate_private_key(curve)

    subject_name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "78"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Saint Petersburg"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ITMO University"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name)
    ])

    assert(not ((signing_issuer is None) ^ (signing_key is None)))

    ca = signing_issuer is None

    if signing_issuer is None:
        signing_issuer = subject_name
    if signing_key is None:
        signing_key = private_key

    chain = (x509.CertificateBuilder()
             .subject_name(subject_name)
             .issuer_name(signing_issuer)
             .public_key(private_key.public_key())
             .serial_number(x509.random_serial_number())
             .not_valid_before(datetime.utcnow())
             .not_valid_after(datetime.utcnow() + timedelta(days=3650))
             .add_extension(AuthorityKeyIdentifier.from_issuer_public_key(signing_key.public_key()), False)
             .add_extension(SubjectKeyIdentifier.from_public_key(private_key.public_key()), False))

    if ca:
        chain = chain.add_extension(BasicConstraints(ca=True, path_length=None), True)

    certificate = chain.sign(signing_key, hashes.SHA256())

    return private_key, certificate


def format_pem_for_conf(pem: bytes) -> str:
    return pem.decode().strip()


def format_pem_for_env(pem: bytes) -> str:
    """Removes header and footer and concatenates all in a single line."""
    return "".join(pem.decode().strip().splitlines()[1:-1])


async def generate_vpn(user_id: int, port: int):
    curve = ec.SECP256R1()
    prefix = f"quirck-{config.APP_MODULE}-{user_id}"

    ca_key, ca_certificate = generate_key_pair(curve, f"{prefix}-server", signing_key=None, signing_issuer=None)

    client_key, client_certificate = generate_key_pair(
        curve, f"{prefix}-client",
        signing_issuer=ca_certificate.issuer,
        signing_key=ca_key
    )

    for platform, directives in [
        ("win", ""),
        ("linux", LINUX_DIRECTIVES)
    ]:
        client_config = BASE.format(
            host=config.VPN_HOST, port=port, directives=directives,
            ca_certificate=format_pem_for_conf(ca_certificate.public_bytes(Encoding.PEM)),
            client_certificate=format_pem_for_conf(client_certificate.public_bytes(Encoding.PEM)),
            client_key=format_pem_for_conf(
                client_key.private_bytes(
                    Encoding.PEM,
                    PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=NoEncryption()
                )
            )
        )

        await s3.upload_bytes(
            config.S3_DEFAULT_BUCKET,
            "vpn", user_id, f"config-{platform}.ovpn",
            client_config.encode()
        )
    
    return {
        "CERT": format_pem_for_env(ca_certificate.public_bytes(Encoding.PEM)),
        "KEY": format_pem_for_env(
            ca_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=NoEncryption()
            )
        )
    }
