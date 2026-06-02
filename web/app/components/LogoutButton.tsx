"use client";

export default function LogoutButton() {
  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "/login";
  }
  return (
    <button onClick={logout} className="text-sm text-gray-500 hover:text-gray-100">
      Lock
    </button>
  );
}
