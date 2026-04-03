import http from "k6/http";
import { check } from "k6";

import { baseUrl } from "./common.js";

export const options = {
  vus: 1,
  iterations: 1,
};

export default function () {
  const expectedAuthFailure = http.expectedStatuses(401, 403);

  const noKeyRes = http.get(`${baseUrl}/api/collections`, {
    responseCallback: expectedAuthFailure,
  });
  check(noKeyRes, {
    "missing api key is rejected": (r) => r.status === 401 || r.status === 403,
  });

  const badKeyRes = http.get(`${baseUrl}/api/collections`, {
    headers: {
      "X-API-Key": "invalid-key",
    },
    responseCallback: expectedAuthFailure,
  });
  check(badKeyRes, {
    "invalid api key is rejected": (r) => r.status === 401 || r.status === 403,
  });
}
