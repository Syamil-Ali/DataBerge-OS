import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const failures = new Rate('failed_requests');
const latency = new Trend('api_latency', true);
const hostHeader = __ENV.HOST_HEADER || 'localhost';

export const options = {
  scenarios: {
    authenticated_reads: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '15s', target: 5 },
        { duration: '30s', target: 10 },
        { duration: '15s', target: 0 },
      ],
    },
  },
  thresholds: {
    failed_requests: ['rate<0.01'],
    api_latency: ['p(95)<1000'],
  },
};

const baseUrl = __ENV.BASE_URL || 'http://127.0.0.1:8000/api';

export function setup() {
  const health = http.get(`${baseUrl}/health/ready`, { headers: { Host: hostHeader } });
  check(health, { 'service ready': (response) => response.status === 200 });
  const login = http.post(`${baseUrl}/auth/login`, JSON.stringify({
    email: __ENV.TEST_EMAIL,
    password: __ENV.TEST_PASSWORD,
  }), { headers: { 'Content-Type': 'application/json', Host: hostHeader } });
  if (login.status !== 200) throw new Error('Load-test login failed');
  const session = login.cookies.db_session?.[0]?.value;
  const csrfCookie = login.cookies.db_csrf?.[0]?.value;
  if (!session || !csrfCookie) throw new Error('Load-test session cookies were not issued');
  return { csrf: login.json('csrf_token'), session, csrfCookie };
}

export default function (data) {
  const response = http.get(`${baseUrl}/projects`, {
    headers: {
      Cookie: `db_session=${data.session}; db_csrf=${data.csrfCookie}`,
      'X-CSRF-Token': data.csrf,
      Host: hostHeader,
    },
  });
  const ok = check(response, { 'projects returned': (result) => result.status === 200 });
  failures.add(!ok);
  latency.add(response.timings.duration);
  sleep(1);
}
