import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const failures = new Rate('distributed_failures');
const baseUrl = __ENV.BASE_URL || 'http://127.0.0.1:8080/api';
const hostHeader = __ENV.HOST_HEADER || 'localhost';

export const options = {
  scenarios: {
    api_read_capacity: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 100,
      stages: [
        { duration: '1m', target: 20 },
        { duration: '3m', target: 50 },
        { duration: '1m', target: 5 },
      ],
    },
  },
  thresholds: {
    distributed_failures: ['rate<0.01'],
    http_req_duration: ['p(95)<750', 'p(99)<1500'],
    http_req_failed: ['rate<0.01'],
  },
};

export function setup() {
  const login = http.post(`${baseUrl}/auth/login`, JSON.stringify({
    email: __ENV.TEST_EMAIL,
    password: __ENV.TEST_PASSWORD,
  }), { headers: { 'Content-Type': 'application/json', Host: hostHeader } });
  if (login.status !== 200) throw new Error('Capacity-test login failed');
  return {
    session: login.cookies.db_session?.[0]?.value,
    csrf: login.cookies.db_csrf?.[0]?.value,
  };
}

export default function (session) {
  const response = http.get(`${baseUrl}/projects`, {
    headers: {
      Cookie: `db_session=${session.session}; db_csrf=${session.csrf}`,
      Host: hostHeader,
    },
    tags: { name: 'GET /api/projects' },
  });
  failures.add(!check(response, { 'authenticated read succeeded': (result) => result.status === 200 }));
  sleep(0.1);
}
