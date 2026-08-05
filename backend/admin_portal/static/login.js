document.querySelector("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#loginError");
  error.textContent = "";
  const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
  const response = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) { error.textContent = (await response.json()).detail || "登录失败"; return; }
  window.location.assign("/");
});
