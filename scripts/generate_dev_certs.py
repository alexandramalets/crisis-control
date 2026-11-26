"""Учебный центр сертификации для стенда TLS.

Создаёт каталог deploy/certs (он в .gitignore). Сертификаты не являются
доверенными в браузере, пока ca.crt не добавлен в корневые центры Windows.

Запуск из корня проекта:
    backend\\.venv\\Scripts\\python.exe scripts\\generate_dev_certs.py
"""

import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deploy" / "certs"
DAYS = 825


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _write_key(path: Path, private_key) -> None:
    path.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))


def _name(common_name: str) -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Crisis Analytics Dev"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])


def _sign(builder: x509.CertificateBuilder, issuer_key) -> x509.Certificate:
    return builder.sign(issuer_key, hashes.SHA256())


def _base(subject_key, issuer_name: x509.Name, common_name: str, sans: list) -> x509.CertificateBuilder:
    now = datetime.now(timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(_name(common_name))
        .issuer_name(issuer_name)
        .public_key(subject_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=DAYS))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(subject_key.public_key()), critical=False)
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ca_key = _key()
    ca_name = _name("Crisis Analytics Dev CA")
    now = datetime.now(timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    ca_ski = ca_cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
    _write_key(OUT / "ca.key", ca_key)
    (OUT / "ca.crt").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))

    loopback = x509.IPAddress(ipaddress.ip_address("127.0.0.1"))
    servers = {
        "backend": [x509.DNSName("backend"), x509.DNSName("localhost"), loopback],
        "analytics": [x509.DNSName("analytics-service"), x509.DNSName("localhost"), loopback],
        "frontend": [x509.DNSName("localhost"), loopback],
        "server": [x509.DNSName("database"), x509.DNSName("localhost"), loopback],
    }
    for filename, sans in servers.items():
        key = _key()
        common_name = sans[0].value
        certificate = _base(key, ca_name, common_name, sans)
        certificate = certificate.add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        certificate = certificate.add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=True,
            data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=False, decipher_only=False,
        ), critical=True)
        certificate = certificate.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False,
        )
        certificate = certificate.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ca_ski), critical=False,
        )
        signed = _sign(certificate, ca_key)
        _write_key(OUT / f"{filename}.key", key)
        (OUT / f"{filename}.crt").write_bytes(signed.public_bytes(serialization.Encoding.PEM))

    print(f"Сертификаты записаны в {OUT}")
    print("Для браузера добавьте deploy\\certs\\ca.crt в доверенные корневые центры сертификации.")


if __name__ == "__main__":
    main()
