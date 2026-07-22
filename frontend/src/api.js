export const API_BASE = "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include", // send/receive the httpOnly session cookie
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

export function login(email, password) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function signup(payload) {
  return request("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout() {
  return request("/auth/logout", { method: "POST" });
}

export function me() {
  return request("/auth/me");
}

export function getFullProfile() {
  return request("/users/me");
}

export function changePassword(currentPassword, newPassword) {
  return request("/users/me/password", {
    method: "PUT",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export function deleteAccount(password) {
  return request("/users/me", {
    method: "DELETE",
    body: JSON.stringify({ password }),
  });
}

export function getPortfolioOverview() {
  return request("/portfolio/overview");
}

export function getClusterPlacement() {
  return request("/portfolio/cluster-placement");
}

export function getRecommendations() {
  return request("/recommendations");
}

export function getMarketStatus(market) {
  return request(`/market/status?market=${market}`);
}

export function getMarketQuotes(symbols, crypto = false) {
  return request(`/market/quotes?symbols=${encodeURIComponent(symbols.join(","))}&crypto=${crypto}`);
}

export function getMarketCandles(symbol, timeframe, limit, crypto = false) {
  return request(
    `/market/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=${limit}&crypto=${crypto}`
  );
}

export function getPsxQuotes(symbols) {
  return request(`/market/psx/quotes?symbols=${encodeURIComponent(symbols.join(","))}`);
}

export function getPsxCandles(symbol, limit) {
  return request(`/market/psx/candles?symbol=${encodeURIComponent(symbol)}&limit=${limit}`);
}

export function saveHoldings(holdingsText) {
  return request("/users/me/holdings", {
    method: "PUT",
    body: JSON.stringify({ holdings_text: holdingsText }),
  });
}

export function clearHoldings() {
  return request("/users/me/holdings", { method: "DELETE" });
}
