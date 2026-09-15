#!/usr/bin/env python3
"""Create/reuse local lab PKI and sync TLS Secrets without writing keys to Git.

Run after Argo CD has created the traefik namespace. Import the public CA into
client trust stores. Re-run for renewal; the tool renews within 30 days of expiry.
"""
import base64
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
STATE = Path.home()/'.local/state/lab-ingress-pki'
STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(STATE, 0o700)
now = dt.datetime.now(dt.timezone.utc)

def keyfile(name):
    p = STATE/name
    if p.exists():
        return serialization.load_pem_private_key(p.read_bytes(), password=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    with os.fdopen(os.open(p, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'wb') as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return key

ca_key = keyfile('ca.key')
ca = x509.load_pem_x509_certificate((STATE/'ca.crt').read_bytes()) if (STATE/'ca.crt').exists() else None
if ca is None or not any(e.oid == x509.ExtensionOID.SUBJECT_KEY_IDENTIFIER for e in ca.extensions):
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Sandbox Lab Ingress CA')])
    ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(minutes=5))
          .not_valid_after(now+dt.timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
          .add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False)
          .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False)
          .sign(ca_key,hashes.SHA256()))
    (STATE/'ca.crt').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
key = keyfile('ingress.key')
# Hostnames come from the Git-managed routes, so adding a route expands the SANs.
import yaml
hosts = []
for p in (ROOT/'ingress/routes').glob('*.yaml'):
    d=yaml.safe_load(p.read_text())
    if d.get('kind') == 'IngressRoute':
        for route in d['spec']['routes']:
            hosts.append(route['match'].split('`')[1])
assert hosts and len(hosts)==len(set(hosts))
cert_path=STATE/'ingress.crt'
cert=x509.load_pem_x509_certificate(cert_path.read_bytes()) if cert_path.exists() else None
existing=set(cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)) if cert else set()
if cert is None or existing!=set(hosts) or cert.not_valid_after_utc<now+dt.timedelta(days=30) or not any(e.oid == x509.ExtensionOID.AUTHORITY_KEY_IDENTIFIER for e in cert.extensions):
    cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Sandbox Lab Ingress')]))
          .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now-dt.timedelta(minutes=5)).not_valid_after(now+dt.timedelta(days=365))
          .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in hosts]),critical=False)
          .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False)
          .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False)
          .add_extension(x509.KeyUsage(True,False,True,False,False,False,False,False,False),critical=True)
          .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
          .sign(ca_key,hashes.SHA256()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

def secret(ns,name,kind,values):
    doc={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':ns},'type':kind,'data':{k:base64.b64encode(v).decode()for k,v in values.items()}}
    subprocess.run(['kubectl','apply','--server-side','--field-manager=lab-ingress-pki','-f','-'],input=json.dumps(doc),text=True,check=True)
secret('traefik','ingress-tls','kubernetes.io/tls',{'tls.crt':cert_path.read_bytes(),'tls.key':(STATE/'ingress.key').read_bytes()})
argo=json.loads(subprocess.check_output(['kubectl','-n','argocd','get','secret','argocd-secret','-o','json']))
secret('argocd','argocd-backend-ca','Opaque',{'ca.crt':base64.b64decode(argo['data']['tls.crt'])})
(ROOT/'ingress/lab-ingress-ca.crt').write_bytes((STATE/'ca.crt').read_bytes())
print('TLS configured for:',', '.join(sorted(hosts)))
print('Public trust certificate:',ROOT/'ingress/lab-ingress-ca.crt')
