import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const headers = readFileSync(new URL('./security-headers.conf', import.meta.url), 'utf8');
const httpTemplate = readFileSync(new URL('./default.conf.template', import.meta.url), 'utf8');
const tlsTemplate = readFileSync(new URL('./tls.conf.template', import.meta.url), 'utf8');

test('клиент задаёт CSP и не открывает default-src для всех', () => {
  assert.match(headers, /Content-Security-Policy/);
  assert.match(headers, /frame-ancestors 'none'/);
  assert.match(headers, /default-src 'self'/);
  assert.doesNotMatch(headers, /default-src \*/);
});

test('HTTP-шаблон не включает HSTS и ограничивает тело запроса', () => {
  assert.doesNotMatch(httpTemplate, /Strict-Transport-Security/);
  assert.match(httpTemplate, /client_max_body_size 10m/);
  assert.match(httpTemplate, /security-headers.conf/);
});

test('TLS-шаблон требует TLS 1.2+ и проверяет сертификат сервера', () => {
  assert.match(tlsTemplate, /ssl_protocols\s+TLSv1\.2 TLSv1\.3/);
  assert.match(tlsTemplate, /Strict-Transport-Security/);
  assert.match(tlsTemplate, /proxy_ssl_verify on/);
  assert.match(tlsTemplate, /proxy_ssl_trusted_certificate \/certs\/ca.crt/);
});
